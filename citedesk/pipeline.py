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
for a draft.

The retrieve stage asks the knowledge base (`citedesk/retrieval.py`), the draft stage writes the
reply (`citedesk/drafting.py`), and the check stage runs the checks in `citedesk/checks.py`,
which decide whether the draft is `ready` for a person or blocked and escalated.
"""

import logging
import sqlite3
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from citedesk import checks, drafting, events, repo, retrieval, review, routing, understand
from citedesk.business import Business
from citedesk.config import Settings
from citedesk.db import connect, transaction
from citedesk.knowledge import KnowledgeBase, KnowledgeBaseError
from citedesk.models import (
    AuditEventType,
    CheckCode,
    Claim,
    Classification,
    Draft,
    DraftKind,
    DraftStatus,
    EscalationSource,
    Extraction,
    Inquiry,
    InquiryStatus,
    Intent,
    ReasonCode,
    Route,
    Screening,
    ScreeningResult,
    Source,
    Stage,
    Urgency,
)
from citedesk.providers import LLMProvider, LLMStepFailed
from citedesk.safety import emergency_hits
from citedesk.screening import screen
from citedesk.state import RETRY_TARGET, transition

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
            focused_signals=found.focused_signals,
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

        # The main reading's flags are kept in the reply it gave (D-041); the focused call's are
        # in their own column (D-075). Both only add reasons.
        flagged = understand.parse_output(classification.raw_response).escalation_signals
        raised = list(
            dict.fromkeys([ReasonCode(code) for code in flagged] + classification.focused_signals)
        )
        decision = routing.decide_route(
            intents=classification.intents,
            primary_confidence=classification.primary_confidence,
            fields=extraction.fields,
            signals=raised,
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


TEMPLATE_MODEL = "template"
TEMPLATE_VERSION = "template-v1"


def _ordered_intents(classification: Classification) -> list[Intent]:
    """The intents with the primary one first, so the most important question is asked first."""
    others = [
        i.intent for i in classification.intents if i.intent is not classification.primary_intent
    ]
    return [classification.primary_intent, *others]


def _questions_for(
    inquiry: Inquiry, classification: Classification, extraction: Extraction
) -> list[retrieval.Question]:
    return retrieval.build_questions(
        intents=_ordered_intents(classification),
        fields=extraction.fields,
        subject=inquiry.subject,
        body=inquiry.body,
        only_open=inquiry.route is Route.request_details,
    )


def _store_checks(
    conn: sqlite3.Connection,
    draft: Draft,
    inquiry: Inquiry,
    business: Business,
    settings: Settings,
    *,
    now: str | None,
) -> list[checks.CheckOutcome]:
    """Run every check on a draft and store the results. The draft becomes `ready` only if no
    blocking check failed (the repository refuses otherwise); a failed one leaves it `blocked`."""
    sources = retrieval.merged_sources(repo.list_retrievals(conn, inquiry.id))
    outcomes = checks.run_checks(
        checks.CheckInput(
            subject=draft.subject,
            body=draft.body,
            claims=draft.claims,
            sources=sources,
            inquiry_text=f"{inquiry.subject or ''}\n{inquiry.body}",
            trusted_text=business.trusted_text,
            kind=draft.kind,
            max_words=settings.draft_max_words,
            system_prompt=drafting.build_system_prompt(business, settings.draft_max_words),
        )
    )
    for outcome in outcomes:
        repo.upsert_draft_check(
            conn,
            draft_id=draft.id,
            check_code=outcome.code,
            blocking=outcome.blocking,
            passed=outcome.passed,
            detail=outcome.detail,
            now=now,
        )
    if not any(o.blocking and not o.passed for o in outcomes):
        repo.set_draft_status(conn, draft.id, DraftStatus.ready)
    return outcomes


def retrieve_stage(
    conn: sqlite3.Connection,
    inquiry_id: int,
    settings: Settings,
    kb: KnowledgeBase,
    business: Business,
    *,
    now: str | None = None,
    request_id: str | None = None,
) -> InquiryStatus:
    """Ask the knowledge base what a `routed` inquiry needs. Safe to run again.

    If it can answer nothing for a reply that needs answers, the inquiry is escalated with
    `NOT_IN_KNOWLEDGE_BASE` and a holding reply is stored for reference. Raises
    `KnowledgeBaseError` when the knowledge base cannot be reached; nothing is drafted then.
    """
    started = time.monotonic()
    inquiry = repo.get_inquiry(conn, inquiry_id)
    if inquiry is None:
        raise LookupError(f"no inquiry {inquiry_id}")
    if inquiry.status is not InquiryStatus.routed or inquiry.route not in (
        Route.draft_reply,
        Route.request_details,
    ):
        return inquiry.status
    if repo.list_retrievals(conn, inquiry_id):
        return inquiry.status  # already done; a crash after this point resumes at the draft
    classification = repo.latest_classification(conn, inquiry_id)
    extraction = repo.latest_extraction(conn, inquiry_id)
    screening = _screening_for(conn, inquiry_id, settings, now)
    if classification is None or extraction is None:
        raise LookupError(f"inquiry {inquiry_id} is routed but has no stored result")
    questions = _questions_for(inquiry, classification, extraction)
    events.record_event(
        conn,
        event_type=AuditEventType.stage_started,
        inquiry_id=inquiry_id,
        stage=Stage.retrieve,
        request_id=request_id,
        now=now,
    )

    # The knowledge base can take many seconds. No transaction is open while we wait.
    got = retrieval.retrieve(kb, questions)

    with transaction(conn):
        current = repo.get_inquiry(conn, inquiry_id)
        if current is None or current.status is not InquiryStatus.routed:
            return InquiryStatus.routed if current is None else current.status
        for answer in got.results:
            repo.insert_retrieval(
                conn,
                inquiry_id=inquiry_id,
                question=answer.question,
                declined=answer.result.declined,
                kb_answer=answer.result.answer,
                sources=answer.result.sources,
                duration_ms=answer.duration_ms,
                now=now,
            )
        final = InquiryStatus.routed
        if inquiry.route is Route.draft_reply and got.all_declined:
            availability_only = not questions and (
                Intent.availability_question in _ordered_intents(classification)
            )
            repo.insert_escalation(
                conn,
                inquiry_id=inquiry_id,
                reason_code=ReasonCode.NOT_IN_KNOWLEDGE_BASE,
                source=EscalationSource.rule,
                detail=(
                    "live availability is not in the documents"
                    if availability_only
                    else "the documents do not cover the question"
                ),
                now=now,
            )
            repo.update_inquiry(conn, inquiry_id, route=Route.escalate, now=now)
            events.record_event(
                conn,
                event_type=AuditEventType.route_decided,
                inquiry_id=inquiry_id,
                stage=Stage.retrieve,
                payload={
                    "route": Route.escalate,
                    "reason_codes": [ReasonCode.NOT_IN_KNOWLEDGE_BASE],
                },
                request_id=request_id,
                now=now,
            )
            holding = drafting.holding_reply(
                business,
                sender_name=inquiry.sender_name,
                subject=inquiry.subject,
                availability=availability_only,
                sensitive_data_masked=screening.sensitive_data_masked,
            )
            draft_id = repo.insert_draft(
                conn,
                inquiry_id=inquiry_id,
                kind=holding.kind,
                subject=holding.subject,
                body=holding.body,
                model=TEMPLATE_MODEL,
                prompt_version=TEMPLATE_VERSION,
                duration_ms=0,
                now=now,
            )
            stored = repo.get_draft(conn, draft_id)
            if stored is None:
                raise RuntimeError("draft was not written")
            _store_checks(conn, stored, inquiry, business, settings, now=now)
            transition(
                conn,
                inquiry_id,
                InquiryStatus.escalated,
                stage=Stage.retrieve,
                request_id=request_id,
                now=now,
            )
            final = InquiryStatus.escalated
        events.record_event(
            conn,
            event_type=AuditEventType.stage_finished,
            inquiry_id=inquiry_id,
            stage=Stage.retrieve,
            payload={
                "questions": len(questions),
                "answered": len(got.answered),
                "declined": len(got.results) - len(got.answered),
                "sources": len(got.sources),
            },
            request_id=request_id,
            duration_ms=int((time.monotonic() - started) * 1000),
            now=now,
        )
        return final


@dataclass(frozen=True)
class _DraftInputs:
    screening: Screening
    sources: list[Source]
    unanswered: list[Intent]
    asking: bool
    missing: list[str]


def _draft_inputs(
    conn: sqlite3.Connection, inquiry: Inquiry, settings: Settings, now: str | None
) -> _DraftInputs:
    """What the model is told when it writes a reply, from what the earlier stages stored."""
    classification = repo.latest_classification(conn, inquiry.id)
    extraction = repo.latest_extraction(conn, inquiry.id)
    screening = _screening_for(conn, inquiry.id, settings, now)
    if classification is None or extraction is None:
        raise LookupError(f"inquiry {inquiry.id} has no stored result")
    rows = repo.list_retrievals(conn, inquiry.id)
    questions = _questions_for(inquiry, classification, extraction)
    unanswered = (
        [q.intent for q, row in zip(questions, rows, strict=True) if row.declined]
        if len(questions) == len(rows)
        else []
    )
    asking = inquiry.route is Route.request_details
    missing = (
        routing.missing_fields(_ordered_intents(classification), extraction.fields)
        if asking
        else []
    )
    return _DraftInputs(screening, retrieval.merged_sources(rows), unanswered, asking, missing)


def draft_stage(
    conn: sqlite3.Connection,
    inquiry_id: int,
    settings: Settings,
    llm: LLMProvider,
    business: Business,
    *,
    now: str | None = None,
    request_id: str | None = None,
) -> InquiryStatus:
    """Write the reply for a `routed` inquiry from what was retrieved. Safe to run again.

    A request for missing details with nothing to answer is a plain template; anything else is
    written by the model from the retrieved passages. The draft is stored `blocked`: it is not
    ready until the check stage has run. Raises `DraftFailed` if the model gives no usable draft.
    """
    started = time.monotonic()
    inquiry = repo.get_inquiry(conn, inquiry_id)
    if inquiry is None:
        raise LookupError(f"no inquiry {inquiry_id}")
    if inquiry.status is not InquiryStatus.routed or inquiry.route not in (
        Route.draft_reply,
        Route.request_details,
    ):
        return inquiry.status
    if repo.latest_draft(conn, inquiry_id) is not None:
        return inquiry.status
    inputs = _draft_inputs(conn, inquiry, settings, now)
    screening, sources, unanswered = inputs.screening, inputs.sources, inputs.unanswered
    asking, missing = inputs.asking, inputs.missing
    events.record_event(
        conn,
        event_type=AuditEventType.stage_started,
        inquiry_id=inquiry_id,
        stage=Stage.draft,
        request_id=request_id,
        now=now,
    )

    model_name, prompt_version, attempts, duration = TEMPLATE_MODEL, TEMPLATE_VERSION, 0, 0
    claims: list[Claim] = []
    if asking and not sources:
        template = drafting.request_details(
            business,
            sender_name=inquiry.sender_name,
            subject=inquiry.subject,
            missing_fields=missing,
            sensitive_data_masked=screening.sensitive_data_masked,
        )
        kind, subject, body = template.kind, template.subject, template.body
    else:
        if not sources:
            raise RuntimeError(f"inquiry {inquiry_id} has nothing retrieved to draft from")
        written = drafting.draft(
            llm,
            business=business,
            sender_name=inquiry.sender_name,
            subject=inquiry.subject,
            body=inquiry.body,
            sources=sources,
            missing_fields=missing,
            unanswered=unanswered,
            sensitive_data_masked=screening.sensitive_data_masked,
            max_words=settings.draft_max_words,
        )
        kind = DraftKind.request_details if asking else DraftKind.reply
        subject = written.output.subject or drafting.reply_subject(inquiry.subject)
        body, claims = written.output.body, written.output.claims
        model_name, prompt_version = written.model, drafting.PROMPT_VERSION
        attempts, duration = written.attempts, written.duration_ms

    with transaction(conn):
        current = repo.get_inquiry(conn, inquiry_id)
        if current is None or current.status is not InquiryStatus.routed:
            return InquiryStatus.routed if current is None else current.status
        repo.insert_draft(
            conn,
            inquiry_id=inquiry_id,
            kind=kind,
            subject=subject,
            body=body,
            claims=claims,
            model=model_name,
            prompt_version=prompt_version,
            duration_ms=duration,
            now=now,
        )
        transition(
            conn,
            inquiry_id,
            InquiryStatus.drafted,
            stage=Stage.draft,
            request_id=request_id,
            now=now,
        )
        events.record_event(
            conn,
            event_type=AuditEventType.stage_finished,
            inquiry_id=inquiry_id,
            stage=Stage.draft,
            payload={
                "kind": kind,
                "version": 1,
                "attempts": attempts,
                "claims": len(claims),
                "words": len(body.split()),
            },
            request_id=request_id,
            duration_ms=int((time.monotonic() - started) * 1000),
            now=now,
        )
    return InquiryStatus.drafted


def _figure_count(outcome: checks.CheckOutcome) -> int:
    return len(outcome.detail.get("ungrounded", []))


def _failure_detail(outcome: checks.CheckOutcome) -> str:
    """A short fixed description of a failed blocking check. No text from the draft."""
    if outcome.code is CheckCode.FIGURES_GROUNDED:
        return f"{_figure_count(outcome)} figure(s) in the draft are not in the sources"
    if outcome.code is CheckCode.NO_COMMITMENT:
        names = ", ".join(outcome.detail.get("matched_patterns", []))
        return f"the draft promises something only staff can: {names}"
    return "the draft repeats instructions or contains a link not in the sources"


def check_stage(
    conn: sqlite3.Connection,
    inquiry_id: int,
    settings: Settings,
    business: Business,
    *,
    now: str | None = None,
    request_id: str | None = None,
) -> InquiryStatus:
    """Run the checks on a `drafted` inquiry's draft. Safe to run again.

    All passing (warnings aside): the draft becomes `ready` and the inquiry waits in
    `needs_review`. A blocking check failing: the draft stays `blocked` and the inquiry is
    `escalated`, with the reason each failed check maps to.
    """
    started = time.monotonic()
    with transaction(conn):
        inquiry = repo.get_inquiry(conn, inquiry_id)
        if inquiry is None:
            raise LookupError(f"no inquiry {inquiry_id}")
        if inquiry.status is not InquiryStatus.drafted:
            return inquiry.status
        draft = repo.latest_draft(conn, inquiry_id)
        if draft is None:
            raise LookupError(f"inquiry {inquiry_id} is drafted but has no draft")
        events.record_event(
            conn,
            event_type=AuditEventType.stage_started,
            inquiry_id=inquiry_id,
            stage=Stage.check,
            request_id=request_id,
            now=now,
        )
        outcomes = _store_checks(conn, draft, inquiry, business, settings, now=now)
        failed = [o for o in outcomes if o.blocking and not o.passed]
        warnings = [o for o in outcomes if not o.blocking and not o.passed]
        for outcome in failed:
            repo.insert_escalation(
                conn,
                inquiry_id=inquiry_id,
                reason_code=checks.reason_for(outcome.code),
                source=EscalationSource.check,
                detail=_failure_detail(outcome),
                now=now,
            )
            events.record_event(
                conn,
                event_type=AuditEventType.check_failed,
                inquiry_id=inquiry_id,
                stage=Stage.check,
                payload={"check": outcome.code, "passed": False},
                request_id=request_id,
                now=now,
            )
        if failed:
            repo.update_inquiry(conn, inquiry_id, route=Route.escalate, now=now)
            events.record_event(
                conn,
                event_type=AuditEventType.route_decided,
                inquiry_id=inquiry_id,
                stage=Stage.check,
                payload={
                    "route": Route.escalate,
                    "reason_codes": [checks.reason_for(o.code) for o in failed],
                },
                request_id=request_id,
                now=now,
            )
        final = InquiryStatus.escalated if failed else InquiryStatus.needs_review
        transition(conn, inquiry_id, final, stage=Stage.check, request_id=request_id, now=now)
        events.record_event(
            conn,
            event_type=AuditEventType.stage_finished,
            inquiry_id=inquiry_id,
            stage=Stage.check,
            payload={
                "blocking_failed": [o.code for o in failed],
                "warnings_failed": [o.code for o in warnings],
            },
            request_id=request_id,
            duration_ms=int((time.monotonic() - started) * 1000),
            now=now,
        )
        return final


STAGE_LABELS = {
    Stage.screen: "Screening",
    Stage.understand: "Understanding",
    Stage.route: "Routing",
    Stage.retrieve: "Retrieval",
    Stage.draft: "Drafting",
    Stage.check: "Checking",
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
        except KnowledgeBaseError as error:
            return _fail(
                conn,
                inquiry_id,
                stage,
                message=f"The knowledge base could not answer ({error.reason})",
                reason=error.reason,
                attempts=1,
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


def redraft_stage(
    conn: sqlite3.Connection,
    draft_id: int,
    guidance: str | None,
    settings: Settings,
    llm: LLMProvider,
    business: Business,
    *,
    now: str | None = None,
    request_id: str | None = None,
) -> InquiryStatus:
    """Write the next version of a rejected draft, following the reviewer's guidance, and check it.

    Only the latest draft of a `rejected` inquiry can be redrafted. The passages are the ones
    already stored, so the knowledge base is not asked again, and with none there is nothing to
    write from (rule 6, docs/RULES.md). The model is called with no transaction open; if the inquiry
    changed meanwhile nothing is written. A model that gives no usable draft raises `DraftFailed`
    and leaves the inquiry `rejected`, so the reviewer can try again.
    """
    note = review.clean_guidance(guidance)
    started = time.monotonic()
    old = repo.get_draft(conn, draft_id)
    inquiry = None if old is None else repo.get_inquiry(conn, old.inquiry_id)
    if old is None or inquiry is None:
        raise review.NotFound("No draft has that id.")
    latest = repo.latest_draft(conn, inquiry.id)
    if (
        inquiry.status is not InquiryStatus.rejected
        or latest is None
        or latest.id != old.id
        or old.status is not DraftStatus.rejected
    ):
        raise review.WrongState("Only the latest rejected draft can be redrafted.")
    inputs = _draft_inputs(conn, inquiry, settings, now)
    if not inputs.sources:
        raise review.WrongState("There are no passages to write a new draft from. Close this item.")
    events.record_event(
        conn,
        event_type=AuditEventType.stage_started,
        inquiry_id=inquiry.id,
        stage=Stage.draft,
        request_id=request_id,
        now=now,
    )
    try:
        written = drafting.draft(
            llm,
            business=business,
            sender_name=inquiry.sender_name,
            subject=inquiry.subject,
            body=inquiry.body,
            sources=inputs.sources,
            missing_fields=inputs.missing,
            unanswered=inputs.unanswered,
            sensitive_data_masked=inputs.screening.sensitive_data_masked,
            max_words=settings.draft_max_words,
            guidance=note,
        )
    except drafting.DraftFailed as error:
        events.record_event(
            conn,
            event_type=AuditEventType.stage_failed,
            inquiry_id=inquiry.id,
            stage=Stage.draft,
            payload={"reason": error.reason, "attempts": error.attempts},
            request_id=request_id,
            now=now,
        )
        raise
    with transaction(conn):
        current = repo.get_inquiry(conn, inquiry.id)
        if current is None or current.status is not InquiryStatus.rejected:
            raise review.WrongState("The inquiry changed while the new draft was written.")
        new_id = repo.insert_draft(
            conn,
            inquiry_id=inquiry.id,
            kind=DraftKind.request_details if inputs.asking else DraftKind.reply,
            subject=written.output.subject or drafting.reply_subject(inquiry.subject),
            body=written.output.body,
            claims=written.output.claims,
            model=written.model,
            prompt_version=drafting.PROMPT_VERSION,
            guidance=note,
            duration_ms=written.duration_ms,
            now=now,
        )
        transition(
            conn,
            inquiry.id,
            InquiryStatus.drafted,
            stage=Stage.draft,
            request_id=request_id,
            now=now,
        )
        new = repo.get_draft(conn, new_id)
        events.record_event(
            conn,
            event_type=AuditEventType.stage_finished,
            inquiry_id=inquiry.id,
            stage=Stage.draft,
            payload={
                "kind": DraftKind.request_details if inputs.asking else DraftKind.reply,
                "version": 0 if new is None else new.version,
                "attempts": written.attempts,
                "claims": len(written.output.claims),
                "words": len(written.output.body.split()),
                "redraft": True,
            },
            request_id=request_id,
            duration_ms=int((time.monotonic() - started) * 1000),
            now=now,
        )
    return _run_stage(
        conn,
        inquiry.id,
        Stage.check,
        lambda: check_stage(conn, inquiry.id, settings, business, now=now, request_id=request_id),
        request_id,
    )


def retry_failed(
    conn: sqlite3.Connection,
    inquiry_id: int,
    *,
    now: str | None = None,
    request_id: str | None = None,
) -> InquiryStatus:
    """Put a `failed` inquiry back where its failed stage started, so the worker runs it again.

    The failure is cleared and an event records which stage is being retried."""
    with transaction(conn):
        inquiry = repo.get_inquiry(conn, inquiry_id)
        if inquiry is None:
            raise review.NotFound("No inquiry has that id.")
        if inquiry.status is not InquiryStatus.failed or inquiry.failure_stage is None:
            raise review.WrongState("Only a failed inquiry can be retried.")
        target = RETRY_TARGET[inquiry.failure_stage]
        transition(conn, inquiry_id, target, request_id=request_id, now=now)
    return target


def process(
    conn: sqlite3.Connection,
    inquiry_id: int,
    settings: Settings,
    *,
    llm: LLMProvider | None = None,
    kb: KnowledgeBase | None = None,
    business: Business | None = None,
    request_id: str | None = None,
) -> InquiryStatus:
    """Run the stages an inquiry still needs, in order, until it rests or fails.

    Without a model only screening runs, so an inquiry waits at `screened`. With one, it goes on
    to `classified` and then to `routed`, `escalated` or `archived`. With a knowledge base and
    the business's details as well, a routed inquiry is retrieved, drafted and checked, and ends
    in `needs_review` or `escalated`.
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
    if llm is None or kb is None or business is None:
        return status
    if status is InquiryStatus.routed:
        status = _run_stage(
            conn,
            inquiry_id,
            Stage.retrieve,
            lambda: retrieve_stage(conn, inquiry_id, settings, kb, business, request_id=request_id),
            request_id,
        )
    if status is InquiryStatus.routed:
        status = _run_stage(
            conn,
            inquiry_id,
            Stage.draft,
            lambda: draft_stage(conn, inquiry_id, settings, llm, business, request_id=request_id),
            request_id,
        )
    if status is InquiryStatus.drafted:
        status = _run_stage(
            conn,
            inquiry_id,
            Stage.check,
            lambda: check_stage(conn, inquiry_id, settings, business, request_id=request_id),
            request_id,
        )
    return status


def run_pending(
    conn: sqlite3.Connection,
    settings: Settings,
    *,
    limit: int | None = None,
    llm: LLMProvider | None = None,
    kb: KnowledgeBase | None = None,
    business: Business | None = None,
) -> list[int]:
    """Process unfinished inquiries one at a time, oldest first. Returns the ids handled.

    Without a model that means `received` ones (screening only). With one it also means
    `screened` and `classified` ones, and with a knowledge base and the business's details also
    `routed` and `drafted` ones. Failed inquiries are left for a deliberate retry.
    """
    statuses = ["received"] if llm is None else ["received", "screened", "classified"]
    if llm is not None and kb is not None and business is not None:
        statuses += ["routed", "drafted"]
    marks = ", ".join("?" for _ in statuses)
    sql = f"SELECT id FROM inquiries WHERE status IN ({marks}) ORDER BY id"  # noqa: S608
    params: list[Any] = list(statuses)
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    handled: list[int] = []
    for row in conn.execute(sql, params).fetchall():
        process(conn, int(row["id"]), settings, llm=llm, kb=kb, business=business)
        handled.append(int(row["id"]))
    return handled


class PipelineWorker:
    """Runs `run_pending` on a background thread, one inquiry at a time.

    It wakes when `notify` is called and otherwise polls, so work that arrived while it was
    stopped is picked up. It uses its own database connection. Given a model it runs every stage
    up to routing; without one it only screens.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        poll_seconds: float = 2.0,
        llm: LLMProvider | None = None,
        kb: KnowledgeBase | None = None,
        business: Business | None = None,
    ) -> None:
        self._settings = settings
        self._llm = llm
        self._kb = kb
        self._business = business
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
                    run_pending(
                        conn, self._settings, llm=self._llm, kb=self._kb, business=self._business
                    )
                except Exception as error:  # noqa: BLE001 (keep the worker alive; log the type only)
                    logger.error("pipeline iteration failed: %s", type(error).__name__)
                self._wake.wait(self._poll)
                self._wake.clear()
        finally:
            conn.close()
