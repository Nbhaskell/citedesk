"""The inquiry status state machine (docs/BACKEND_SCHEMA.md section 5).

`ALLOWED` is every move except a retry from `failed`, which goes back to where the failed stage
started and so depends on `failure_stage`. Nothing else may change an inquiry's status.
"""

import re
import sqlite3

from citedesk.db import transaction, utc_now
from citedesk.events import record_event
from citedesk.models import AuditEventType, Stage
from citedesk.models import InquiryStatus as S

MAX_FAILURE_MESSAGE = 300
QUOTE_WINDOW = 20  # characters of the customer's text that may not appear in a failure message

ALLOWED: frozenset[tuple[S, S]] = frozenset(
    {
        (S.received, S.screened),
        (S.received, S.failed),
        (S.screened, S.classified),
        (S.screened, S.archived),
        (S.screened, S.escalated),
        (S.screened, S.failed),
        (S.classified, S.routed),
        (S.classified, S.failed),
        (S.routed, S.escalated),
        (S.routed, S.archived),
        (S.routed, S.drafted),
        (S.routed, S.failed),
        (S.drafted, S.needs_review),
        (S.drafted, S.escalated),
        (S.needs_review, S.approved),
        (S.needs_review, S.rejected),
        (S.needs_review, S.escalated),
        (S.approved, S.exported),
        (S.rejected, S.drafted),
        (S.rejected, S.resolved),
        (S.escalated, S.resolved),
    }
)

# A retry from `failed` returns to the status the failed stage started from.
RETRY_TARGET: dict[Stage, S] = {
    Stage.screen: S.received,
    Stage.understand: S.screened,
    Stage.route: S.classified,
    Stage.retrieve: S.routed,
    Stage.draft: S.routed,
}

# The stages that can fail from each status: exactly those whose retry returns to that status.
FAILURE_STAGES: dict[S, frozenset[Stage]] = {
    status: frozenset(stage for stage, target in RETRY_TARGET.items() if target is status)
    for status in set(RETRY_TARGET.values())
}


class InvalidTransition(Exception):
    """The requested status change is not in the state machine."""


def allowed_next(status: S, failure_stage: Stage | None = None) -> frozenset[S]:
    """Statuses reachable in one move. From `failed` this depends on the stage that failed."""
    if status is S.failed:
        target = RETRY_TARGET.get(failure_stage) if failure_stage is not None else None
        return frozenset() if target is None else frozenset({target})
    return frozenset(to for source, to in ALLOWED if source is status)


def check_transition(from_status: S, to_status: S, failure_stage: Stage | None = None) -> None:
    from_status, to_status = S(from_status), S(to_status)
    if to_status not in allowed_next(from_status, failure_stage):
        raise InvalidTransition(
            f"cannot move an inquiry from {from_status.value} to {to_status.value}"
        )


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _quotes_the_customer(note: str, texts: list[str | None]) -> bool:
    """True if a run of the customer's own words appears in the note."""
    haystack = _normalise(note)
    for text in texts:
        if not text or len(_normalise(text)) < 8:
            continue
        words = _normalise(text)
        window = min(QUOTE_WINDOW, len(words))
        if any(words[i : i + window] in haystack for i in range(len(words) - window + 1)):
            return True
    return False


def transition(
    conn: sqlite3.Connection,
    inquiry_id: int,
    to_status: S | str,
    *,
    stage: Stage | str | None = None,
    failure_stage: Stage | str | None = None,
    failure_message: str | None = None,
    request_id: str | None = None,
    duration_ms: int | None = None,
    now: str | None = None,
) -> None:
    """Move an inquiry to a new status. The only code that changes `inquiries.status`.

    Checks the move against the state machine, updates the status and failure fields, and writes
    a `status_changed` audit event, all in one transaction. A move to `failed` needs the stage that
    failed (valid for the current status) and a short message with no customer text. A retry from
    `failed` returns to where that stage started and clears the failure.
    """
    target = S(to_status)
    failed_at: Stage | None = None
    if target is S.failed:
        if failure_stage is None:
            raise ValueError("failure_stage is required when moving to failed")
        if not failure_message:
            raise ValueError("failure_message is required when moving to failed")
        if len(failure_message) > MAX_FAILURE_MESSAGE:
            raise ValueError(f"failure_message must be at most {MAX_FAILURE_MESSAGE} characters")
        failed_at = Stage(failure_stage)
    elif failure_stage is not None or failure_message is not None:
        raise ValueError("failure_stage and failure_message are only allowed when moving to failed")

    with transaction(conn):
        row = conn.execute(
            "SELECT status, failure_stage, body, subject FROM inquiries WHERE id = ?", (inquiry_id,)
        ).fetchone()
        if row is None:
            raise LookupError(f"no inquiry {inquiry_id}")
        current = S(row["status"])
        recorded = Stage(row["failure_stage"]) if row["failure_stage"] else None
        check_transition(current, target, recorded)

        new_stage: str | None = None
        new_message: str | None = None
        payload: dict[str, str] = {}
        if failed_at is not None:
            if failed_at not in FAILURE_STAGES.get(current, frozenset()):
                raise InvalidTransition(
                    f"an inquiry in status {current.value} cannot fail at stage {failed_at.value}"
                )
            if failure_message and _quotes_the_customer(
                failure_message, [row["body"], row["subject"]]
            ):
                raise ValueError("failure_message must not contain message text")
            new_stage, new_message = failed_at.value, failure_message
            payload = {"failure_stage": failed_at.value}
        elif current is S.failed and recorded is not None:
            payload = {"retry_of_stage": recorded.value}

        stamp = now or utc_now()
        conn.execute(
            "UPDATE inquiries SET status = ?, failure_stage = ?, failure_message = ?, "
            "updated_at = ? WHERE id = ?",
            (target.value, new_stage, new_message, stamp, inquiry_id),
        )
        record_event(
            conn,
            event_type=AuditEventType.status_changed,
            inquiry_id=inquiry_id,
            stage=stage,
            from_status=current,
            to_status=target,
            payload=payload,
            request_id=request_id,
            duration_ms=duration_ms,
            now=stamp,
        )
