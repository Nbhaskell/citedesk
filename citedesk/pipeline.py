"""The pipeline worker: the screen, understand and route stages, and the loop that runs them.

Each stage does its writes in one transaction, so a crash leaves the inquiry exactly as it was and
it can then fail cleanly at that stage. The understand stage is the exception to "one transaction
for everything": it waits for the model with no transaction open, so a slow model never holds the
database's write lock, and writes what it learned afterwards in one transaction. Later phases add
the retrieve, draft and check stages after these.

What the screen stage does with each result:

- a duplicate message is archived and stays linked to the original;
- suspected injection is escalated with `INJECTION_SUSPECTED` before any model reads it, and if an
  emergency term is also present it gets `HEALTH_SAFETY` and urgent priority, because no model
  will look at it;
- spam is archived, unless the sender has an earlier clean inquiry (a known customer);
- anything else becomes `screened` and waits for the next stage.

The understand stage has the model classify and extract (`citedesk/understand.py`) and moves the
inquiry to `classified`. The route stage applies the rules in `citedesk/routing.py`: it records
every escalation reason and moves the inquiry to `escalated`, `archived`, or leaves it at `routed`
for a draft (Phase 5).
"""

import logging
import sqlite3
import threading
import time
from collections.abc import Callable
from typing import Any

from citedesk import events, repo, routing, understand
from citedesk.config import Settings
from citedesk.db import connect, transaction
from citedesk.models import (
    AuditEventType,
    EscalationSource,
    InquiryStatus,
    ReasonCode,
    Route,
    Screening,
    ScreeningResult,
    Stage,
    Urgency,
)
from citedesk.providers import LLMProvider, LLMStepFailed
from citedesk.safety import emergency_hits
from citedesk.screening import screen
from citedesk.state import transition

logger = logging.getLogger("citedesk.pipeline")


def _screening_for(
    conn: sqlite3.Connection, inquiry_id: int, settings: Settings, now: str | None
) -> Screening:
    """The stored screening row; recomputed from the stored text if, unusually, there is none."""
    existing = repo.get_screening(conn, inquiry_id)
    if existing is not None:
        return existing
    inquiry = repo.get_inquiry(conn, inquiry_id)
    if inquiry is None:
        raise LookupError(f"no inquiry {inquiry_id}")
    outcome = screen(inquiry.subject, inquiry.body, spam_threshold=settings.spam_threshold)
    repo.upsert_screening(
        conn,
        inquiry_id=inquiry_id,
        spam_score=outcome.spam_score,
        injection_flags=outcome.injection_flags,
        sensitive_data_masked=bool(outcome.sensitive_kinds),
        result=outcome.result,
        now=now,
    )
    stored = repo.get_screening(conn, inquiry_id)
    if stored is None:
        raise RuntimeError("screening row was not written")
    return stored


def screen_stage(
    conn: sqlite3.Connection,
    inquiry_id: int,
    settings: Settings,
    *,
    now: str | None = None,
    request_id: str | None = None,
) -> InquiryStatus:
    """Apply the stored screening result to a `received` inquiry. Safe to run again."""
    started = time.monotonic()
    with transaction(conn):
        inquiry = repo.get_inquiry(conn, inquiry_id)
        if inquiry is None:
            raise LookupError(f"no inquiry {inquiry_id}")
        if inquiry.status is not InquiryStatus.received:
            return inquiry.status

        screening = _screening_for(conn, inquiry_id, settings, now)
        events.record_event(
            conn,
            event_type=AuditEventType.stage_started,
            inquiry_id=inquiry_id,
            stage=Stage.screen,
            request_id=request_id,
            now=now,
        )
        text = f"{inquiry.subject or ''}\n{inquiry.body}"
        terms = emergency_hits(text)
        known = repo.has_clean_history(conn, inquiry.sender_email, exclude_id=inquiry_id)

        payload: dict[str, Any] = {
            "result": screening.result.value,
            "spam_score": screening.spam_score,
            "sensitive_data_masked": screening.sensitive_data_masked,
        }
        transition(
            conn,
            inquiry_id,
            InquiryStatus.screened,
            stage=Stage.screen,
            request_id=request_id,
            now=now,
        )

        final = InquiryStatus.screened
        if inquiry.duplicate_of is not None:
            payload["duplicate_of"] = inquiry.duplicate_of
            repo.update_inquiry(conn, inquiry_id, route=Route.archive, now=now)
            final = InquiryStatus.archived
        elif screening.result is ScreeningResult.injection_suspected:
            payload["injection_flags"] = list(screening.injection_flags)
            repo.insert_escalation(
                conn,
                inquiry_id=inquiry_id,
                reason_code=ReasonCode.INJECTION_SUSPECTED,
                source=EscalationSource.rule,
                detail="patterns: " + ", ".join(screening.injection_flags),
                now=now,
            )
            fields: dict[str, Any] = {"route": Route.escalate}
            if terms:
                payload["emergency_terms"] = terms
                repo.insert_escalation(
                    conn,
                    inquiry_id=inquiry_id,
                    reason_code=ReasonCode.HEALTH_SAFETY,
                    source=EscalationSource.safety_net,
                    detail="terms: " + ", ".join(terms),
                    now=now,
                )
                fields["urgency"] = Urgency.urgent
            repo.update_inquiry(conn, inquiry_id, now=now, **fields)
            final = InquiryStatus.escalated
        elif screening.result is ScreeningResult.spam:
            payload["known_sender"] = known
            if not known:
                repo.update_inquiry(conn, inquiry_id, route=Route.archive, now=now)
                final = InquiryStatus.archived

        elapsed = int((time.monotonic() - started) * 1000)
        if final is not InquiryStatus.screened:
            transition(conn, inquiry_id, final, stage=Stage.screen, request_id=request_id, now=now)
        events.record_event(
            conn,
            event_type=AuditEventType.stage_finished,
            inquiry_id=inquiry_id,
            stage=Stage.screen,
            payload=payload,
            request_id=request_id,
            duration_ms=elapsed,
            now=now,
        )
        return final


def understand_stage(
    conn: sqlite3.Connection,
    inquiry_id: int,
    settings: Settings,
    llm: LLMProvider,
    *,
    now: str | None = None,
    request_id: str | None = None,
) -> InquiryStatus:
    """Have the model read a `screened` inquiry, then store what it found. Safe to run again.

    Raises `UnderstandFailed` if the model gives no usable reply; nothing is written then except
    the `stage_started` event.
    """
    started = time.monotonic()
    inquiry = repo.get_inquiry(conn, inquiry_id)
    if inquiry is None:
        raise LookupError(f"no inquiry {inquiry_id}")
    if inquiry.status is not InquiryStatus.screened:
        return inquiry.status
    events.record_event(
        conn,
        event_type=AuditEventType.stage_started,
        inquiry_id=inquiry_id,
        stage=Stage.understand,
        request_id=request_id,
        now=now,
    )

    # The model can take a minute or more. No transaction is open while we wait for it.
    found = understand.understand(
        llm,
        subject=inquiry.subject,
        body=inquiry.body,
        received_at=inquiry.received_at,
        enable_thinking=settings.enable_thinking,
    )
    output = found.output

    with transaction(conn):
        current = repo.get_inquiry(conn, inquiry_id)
        if current is None or current.status is not InquiryStatus.screened:
            return InquiryStatus.screened if current is None else current.status
        classification_id = repo.insert_classification(
            conn,
            inquiry_id=inquiry_id,
            model=found.model,
            prompt_version=understand.PROMPT_VERSION,
            intents=output.intents,
            primary_intent=output.primary_intent,
            primary_confidence=found.primary_confidence,
            urgency=found.urgency,
            sentiment=output.sentiment,
            summary=output.summary,
            safety_net_hit=found.safety_net_hit,
            raw_response=found.raw_response,
            duration_ms=found.duration_ms,
            now=now,
        )
        repo.insert_extraction(
            conn,
            inquiry_id=inquiry_id,
            classification_id=classification_id,
            fields=found.fields,
            missing_fields=found.missing_fields,
            now=now,
        )
        repo.update_inquiry(
            conn, inquiry_id, primary_intent=output.primary_intent, urgency=found.urgency, now=now
        )
        transition(
            conn,
            inquiry_id,
            InquiryStatus.classified,
            stage=Stage.understand,
            request_id=request_id,
            now=now,
        )
        events.record_event(
            conn,
            event_type=AuditEventType.stage_finished,
            inquiry_id=inquiry_id,
            stage=Stage.understand,
            payload={
                "primary_intent": output.primary_intent,
                "primary_confidence": found.primary_confidence,
                "urgency": found.urgency,
                "intents": [item.intent for item in output.intents],
                "signals": found.signals,
                "missing_fields": found.missing_fields,
                "safety_net": found.safety_net_hit,
                "attempts": found.attempts,
                "notes": found.notes,
            },
            request_id=request_id,
            duration_ms=int((time.monotonic() - started) * 1000),
            now=now,
        )
    return InquiryStatus.classified


def route_stage(
    conn: sqlite3.Connection,
    inquiry_id: int,
    settings: Settings,
    *,
    now: str | None = None,
    request_id: str | None = None,
) -> InquiryStatus:
    """Apply the routing rules to a `classified` inquiry. Safe to run again.

    The inquiry ends `escalated` or `archived`, or stays `routed` to wait for a reply to be
    drafted. Reads only what the understand stage stored, so it never calls the model.
    """
    started = time.monotonic()
    with transaction(conn):
        inquiry = repo.get_inquiry(conn, inquiry_id)
        if inquiry is None:
            raise LookupError(f"no inquiry {inquiry_id}")
        if inquiry.status is not InquiryStatus.classified:
            return inquiry.status
        classification = repo.latest_classification(conn, inquiry_id)
        extraction = repo.latest_extraction(conn, inquiry_id)
        if classification is None or extraction is None:
            raise LookupError(f"inquiry {inquiry_id} is classified but has no stored result")
        screening = _screening_for(conn, inquiry_id, settings, now)
        events.record_event(
            conn,
            event_type=AuditEventType.stage_started,
            inquiry_id=inquiry_id,
            stage=Stage.route,
            request_id=request_id,
            now=now,
        )

        # The three flags the model may raise are kept in the reply it gave, not in a column.
        flagged = understand.parse_output(classification.raw_response).escalation_signals
        decision = routing.decide_route(
            intents=classification.intents,
            primary_confidence=classification.primary_confidence,
            fields=extraction.fields,
            signals=[ReasonCode(code) for code in flagged],
            screening_result=screening.result,
            safety_net_hit=classification.safety_net_hit,
            escalate_on_low_confidence=settings.escalate_on_low_confidence,
        )

        transition(
            conn,
            inquiry_id,
            InquiryStatus.routed,
            stage=Stage.route,
            request_id=request_id,
            now=now,
        )
        for reason in decision.reasons:
            repo.insert_escalation(
                conn,
                inquiry_id=inquiry_id,
                reason_code=reason.code,
                source=reason.source,
                detail=reason.detail,
                now=now,
            )
        repo.update_inquiry(conn, inquiry_id, route=decision.route, now=now)
        events.record_event(
            conn,
            event_type=AuditEventType.route_decided,
            inquiry_id=inquiry_id,
            stage=Stage.route,
            payload={
                "route": decision.route,
                "reason_codes": decision.reason_codes,
                "missing_fields": list(decision.missing_fields),
                "safety_net": classification.safety_net_hit,
            },
            request_id=request_id,
            now=now,
        )
        final = InquiryStatus.routed
        if decision.route is Route.escalate:
            final = InquiryStatus.escalated
        elif decision.route is Route.archive:
            final = InquiryStatus.archived
        if final is not InquiryStatus.routed:
            transition(conn, inquiry_id, final, stage=Stage.route, request_id=request_id, now=now)
        events.record_event(
            conn,
            event_type=AuditEventType.stage_finished,
            inquiry_id=inquiry_id,
            stage=Stage.route,
            payload={"route": decision.route},
            request_id=request_id,
            duration_ms=int((time.monotonic() - started) * 1000),
            now=now,
        )
        return final


STAGE_LABELS = {
    Stage.screen: "Screening",
    Stage.understand: "Understanding",
    Stage.route: "Routing",
}


def _fail(
    conn: sqlite3.Connection,
    inquiry_id: int,
    stage: Stage,
    *,
    message: str,
    reason: str,
    attempts: int,
    request_id: str | None,
) -> InquiryStatus:
    """Record that a stage gave up. The message and reason hold no text from the inquiry."""
    with transaction(conn):
        events.record_event(
            conn,
            event_type=AuditEventType.stage_failed,
            inquiry_id=inquiry_id,
            stage=stage,
            payload={"reason": reason, "attempts": attempts},
            request_id=request_id,
        )
        transition(
            conn,
            inquiry_id,
            InquiryStatus.failed,
            stage=stage,
            failure_stage=stage,
            failure_message=message,
            request_id=request_id,
        )
    return InquiryStatus.failed


def _run_stage(
    conn: sqlite3.Connection,
    inquiry_id: int,
    stage: Stage,
    call: Callable[[], InquiryStatus],
    request_id: str | None,
) -> InquiryStatus:
    """Run a stage; after a crash run it once more, then mark the inquiry failed.

    A model that gave no usable reply has already had its own retry (TRD 4.2), so that is not
    run a second time.
    """
    last: Exception | None = None
    for _attempt in (1, 2):
        try:
            return call()
        except LLMStepFailed as error:
            return _fail(
                conn,
                inquiry_id,
                stage,
                message=f"The model gave no usable reply ({error.reason})",
                reason=error.reason,
                attempts=error.attempts,
                request_id=request_id,
            )
        except Exception as error:  # noqa: BLE001 (any failure is retried, then recorded)
            last = error
            logger.warning(
                "%s stage failed for inquiry %s: %s", stage.value, inquiry_id, type(error).__name__
            )
    return _fail(
        conn,
        inquiry_id,
        stage,
        message=f"{STAGE_LABELS[stage]} crashed twice ({type(last).__name__})",
        reason="crashed",
        attempts=2,
        request_id=request_id,
    )


def process(
    conn: sqlite3.Connection,
    inquiry_id: int,
    settings: Settings,
    *,
    llm: LLMProvider | None = None,
    request_id: str | None = None,
) -> InquiryStatus:
    """Run the stages an inquiry still needs, in order, until it rests or fails.

    Without a model only screening runs, so an inquiry waits at `screened`. With one, it goes on
    to `classified` and then to `routed`, `escalated` or `archived`.
    """
    status = _run_stage(
        conn,
        inquiry_id,
        Stage.screen,
        lambda: screen_stage(conn, inquiry_id, settings, request_id=request_id),
        request_id,
    )
    if llm is not None and status is InquiryStatus.screened:
        status = _run_stage(
            conn,
            inquiry_id,
            Stage.understand,
            lambda: understand_stage(conn, inquiry_id, settings, llm, request_id=request_id),
            request_id,
        )
    if llm is not None and status is InquiryStatus.classified:
        status = _run_stage(
            conn,
            inquiry_id,
            Stage.route,
            lambda: route_stage(conn, inquiry_id, settings, request_id=request_id),
            request_id,
        )
    return status


def run_pending(
    conn: sqlite3.Connection,
    settings: Settings,
    *,
    limit: int | None = None,
    llm: LLMProvider | None = None,
) -> list[int]:
    """Process unfinished inquiries one at a time, oldest first. Returns the ids handled.

    Without a model that means `received` ones (screening only). With one it also means
    `screened` and `classified` ones. Failed inquiries are left for a deliberate retry.
    """
    statuses = ["received"] if llm is None else ["received", "screened", "classified"]
    marks = ", ".join("?" for _ in statuses)
    sql = f"SELECT id FROM inquiries WHERE status IN ({marks}) ORDER BY id"  # noqa: S608
    params: list[Any] = list(statuses)
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    handled: list[int] = []
    for row in conn.execute(sql, params).fetchall():
        process(conn, int(row["id"]), settings, llm=llm)
        handled.append(int(row["id"]))
    return handled


class PipelineWorker:
    """Runs `run_pending` on a background thread, one inquiry at a time.

    It wakes when `notify` is called and otherwise polls, so work that arrived while it was
    stopped is picked up. It uses its own database connection. Given a model it runs every stage
    up to routing; without one it only screens.
    """

    def __init__(
        self, settings: Settings, *, poll_seconds: float = 2.0, llm: LLMProvider | None = None
    ) -> None:
        self._settings = settings
        self._llm = llm
        self._poll = poll_seconds
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="citedesk-pipeline", daemon=True)
        self._thread.start()

    def notify(self) -> None:
        self._wake.set()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None

    def _run(self) -> None:
        conn = connect(self._settings.db_path)
        try:
            while not self._stop.is_set():
                try:
                    run_pending(conn, self._settings, llm=self._llm)
                except Exception as error:  # noqa: BLE001 (keep the worker alive; log the type only)
                    logger.error("pipeline iteration failed: %s", type(error).__name__)
                self._wake.wait(self._poll)
                self._wake.clear()
        finally:
            conn.close()
