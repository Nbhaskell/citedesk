"""Shared builders for tests that need a scripted model reply."""

import sqlite3
from typing import Any

from citedesk import repo
from citedesk.models import CheckCode, DraftStatus, InquiryStatus, ReasonCode
from citedesk.routing import MODEL_SIGNALS
from citedesk.state import transition

S = InquiryStatus
T1 = "2026-10-28T10:00:00Z"
DRAFT_BODY = "Hello,\n\nA drain clearing starts at $175.\n\nKind regards,\nBrightwater"

FIELD_KEYS = (
    "service_type",
    "start_date",
    "property_type",
    "address_area",
    "preferred_contact",
    "booking_reference",
    "dates_as_written",
)


def model_reply(**over: Any) -> dict[str, Any]:
    """A valid reply from the understand prompt: a plain drain-price question."""
    base: dict[str, Any] = {
        "summary": "Asks how much a kitchen drain costs.",
        "intents": [{"intent": "pricing_question", "confidence": "high"}],
        "primary_intent": "pricing_question",
        "urgency": "normal",
        "sentiment": "neutral",
        "escalation_signals": [],
        "fields": dict.fromkeys(FIELD_KEYS) | {"service_type": "drain_cleaning"},
    }
    base.update(over)
    return base


def perfect_reply(item: dict[str, Any]) -> dict[str, Any]:
    """What a model that read the golden labels would say, for an end-to-end test."""
    labels = item["labels"]
    reasons = {ReasonCode(code) for code in labels["expected_reason_codes"]}
    confidence = "low" if ReasonCode.LOW_CONFIDENCE in reasons else "high"
    return {
        "summary": "A customer message.",
        "intents": [{"intent": name, "confidence": confidence} for name in labels["intents"]],
        "primary_intent": labels["primary_intent"],
        "urgency": labels["urgency"],
        "sentiment": "neutral",
        "escalation_signals": sorted(code.value for code in reasons & MODEL_SIGNALS),
        "fields": dict.fromkeys(FIELD_KEYS) | labels["fields"],
    }


def walk(conn: sqlite3.Connection, inquiry_id: int, *path: S) -> None:
    for step in path:
        transition(conn, inquiry_id, step, now=T1)


def in_review(conn: sqlite3.Connection, *, blocked: bool = False) -> tuple[int, int]:
    """An inquiry waiting for review with a ready draft (or a blocked one that escalated)."""
    inquiry_id = repo.insert_inquiry(
        conn, channel="web_form", body="How much for a drain?", sender_name="Alex", now=T1
    )
    walk(conn, inquiry_id, S.screened, S.classified, S.routed, S.drafted)
    draft_id = repo.insert_draft(
        conn,
        inquiry_id=inquiry_id,
        kind="reply",
        subject="Re: Drain",
        body=DRAFT_BODY,
        model="fake",
        prompt_version="draft-v1",
        now=T1,
    )
    repo.upsert_draft_check(
        conn,
        draft_id=draft_id,
        check_code=CheckCode.FIGURES_GROUNDED,
        blocking=True,
        passed=not blocked,
        now=T1,
    )
    if blocked:
        walk(conn, inquiry_id, S.escalated)
    else:
        repo.set_draft_status(conn, draft_id, DraftStatus.ready)
        walk(conn, inquiry_id, S.needs_review)
    return inquiry_id, draft_id
