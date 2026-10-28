"""The pipeline worker, as far as Phase 3 goes: the screen stage and the loop that runs it.

`screen_stage` applies the screening result that intake stored. It does all of its work in one
transaction, so a crash leaves the inquiry exactly as it was (`received`) and it can then fail
cleanly at the `screen` stage. Later phases add the understand, route, retrieve, draft and check
stages after it.

What the stage does with each result:

- a duplicate message is archived and stays linked to the original;
- suspected injection is escalated with `INJECTION_SUSPECTED` before any model reads it, and if an
  emergency term is also present it gets `HEALTH_SAFETY` and urgent priority, because no model
  will look at it;
- spam is archived, unless the sender has an earlier clean inquiry (a known customer);
- anything else becomes `screened` and waits for the next stage.
"""

import logging
import sqlite3
import threading
import time
from typing import Any

from citedesk import events, repo
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


def process(
    conn: sqlite3.Connection, inquiry_id: int, settings: Settings, *, request_id: str | None = None
) -> InquiryStatus:
    """Run the screen stage, retrying once. After a second crash the inquiry is marked failed."""
    last: Exception | None = None
    for _attempt in (1, 2):
        try:
            return screen_stage(conn, inquiry_id, settings, request_id=request_id)
        except Exception as error:  # noqa: BLE001 (any failure is retried, then recorded)
            last = error
            logger.warning(
                "screen stage failed for inquiry %s: %s", inquiry_id, type(error).__name__
            )
    transition(
        conn,
        inquiry_id,
        InquiryStatus.failed,
        stage=Stage.screen,
        failure_stage=Stage.screen,
        failure_message=f"Screening crashed twice ({type(last).__name__})",
        request_id=request_id,
    )
    return InquiryStatus.failed


def run_pending(
    conn: sqlite3.Connection, settings: Settings, *, limit: int | None = None
) -> list[int]:
    """Process `received` inquiries one at a time, oldest first. Returns the ids handled."""
    sql = "SELECT id FROM inquiries WHERE status = 'received' ORDER BY id"
    rows = conn.execute(
        sql + (" LIMIT ?" if limit is not None else ""), (limit,) if limit is not None else ()
    ).fetchall()
    handled: list[int] = []
    for row in rows:
        process(conn, int(row["id"]), settings)
        handled.append(int(row["id"]))
    return handled


class PipelineWorker:
    """Runs `run_pending` on a background thread, one inquiry at a time.

    It wakes when `notify` is called and otherwise polls, so work that arrived while it was
    stopped is picked up. It uses its own database connection.
    """

    def __init__(self, settings: Settings, *, poll_seconds: float = 2.0) -> None:
        self._settings = settings
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
                    run_pending(conn, self._settings)
                except Exception as error:  # noqa: BLE001 (keep the worker alive; log the type only)
                    logger.error("pipeline iteration failed: %s", type(error).__name__)
                self._wake.wait(self._poll)
                self._wake.clear()
        finally:
            conn.close()
