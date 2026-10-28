"""What a reviewer can do with an inquiry: approve (with or without an edit), reject, escalate,
resolve, and copy the approved text (docs/APP_FLOW.md 4.7 and 4.8).

Every decision is one transaction: the draft status, the inquiry status, the `reviews` row and an
audit event succeed or fail together. The audit event holds the decision code and the draft id,
never the reviewer's note or edit (CLAUDE.md rule 4); those live in `reviews` only. Nothing here
sends anything: `export` records that the text was copied.
"""

import re
import sqlite3
from dataclasses import dataclass

from citedesk import events, repo
from citedesk.db import transaction
from citedesk.models import (
    AuditEventType,
    Decision,
    Draft,
    DraftStatus,
    EscalationSource,
    ExportMethod,
    Inquiry,
    InquiryStatus,
    ReasonCode,
    Review,
)
from citedesk.state import transition

MAX_EDITED_CHARS = 10_000
MAX_NOTE_CHARS = 500
MAX_REVIEW_SECONDS = 86_400
CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
MANUAL_DETAIL = "Escalated by the reviewer; the note is in the review record."

S = InquiryStatus


class ReviewError(Exception):
    """Base for refusals. The message never repeats text the reviewer sent."""


class NotFound(ReviewError):
    """No draft or inquiry has that id."""


class WrongState(ReviewError):
    """The inquiry or draft is not in a state where this decision is possible."""


class InvalidReview(ReviewError):
    """The reviewer's input is missing or out of range."""


@dataclass(frozen=True)
class ApprovedText:
    inquiry_id: int
    draft_id: int
    subject: str | None
    body: str


def _clean_note(note: str | None, *, required: bool, what: str) -> str | None:
    text = (note or "").strip()
    if not text:
        if required:
            raise InvalidReview(f"A {what} is required.")
        return None
    if len(text) > MAX_NOTE_CHARS or CONTROL_CHARACTERS.search(text):
        raise InvalidReview(f"The {what} is too long or holds characters that are not allowed.")
    return text


def _check_seconds(seconds: int | None) -> None:
    if seconds is not None and not 0 <= seconds <= MAX_REVIEW_SECONDS:
        raise InvalidReview("The review time is out of range.")


def _draft_and_inquiry(conn: sqlite3.Connection, draft_id: int) -> tuple[Draft, Inquiry]:
    draft = repo.get_draft(conn, draft_id)
    inquiry = None if draft is None else repo.get_inquiry(conn, draft.inquiry_id)
    if draft is None or inquiry is None:
        raise NotFound("No draft has that id.")
    return draft, inquiry


def _inquiry(conn: sqlite3.Connection, inquiry_id: int) -> Inquiry:
    inquiry = repo.get_inquiry(conn, inquiry_id)
    if inquiry is None:
        raise NotFound("No inquiry has that id.")
    return inquiry


def _require_open_draft(conn: sqlite3.Connection, draft: Draft, inquiry: Inquiry) -> None:
    latest = repo.latest_draft(conn, inquiry.id)
    if (
        inquiry.status is not S.needs_review
        or latest is None
        or latest.id != draft.id
        or draft.status is not DraftStatus.ready
    ):
        raise WrongState("This draft is not waiting for a decision.")


def _record(
    conn: sqlite3.Connection,
    inquiry_id: int,
    decision: Decision,
    *,
    draft_id: int | None,
    edited_body: str | None = None,
    reason: str | None = None,
    review_seconds: int | None = None,
    request_id: str | None,
    now: str | None,
) -> Review:
    review_id = repo.insert_review(
        conn,
        inquiry_id=inquiry_id,
        draft_id=draft_id,
        decision=decision,
        edited_body=edited_body,
        reason=reason,
        review_seconds=review_seconds,
        now=now,
    )
    payload: dict[str, str | int] = {"decision": decision.value}
    if draft_id is not None:
        payload["draft_id"] = draft_id
    events.record_event(
        conn,
        event_type=AuditEventType.review_recorded,
        inquiry_id=inquiry_id,
        payload=payload,
        request_id=request_id,
        now=now,
    )
    return next(r for r in repo.list_reviews(conn, inquiry_id) if r.id == review_id)


def approve(
    conn: sqlite3.Connection,
    draft_id: int,
    *,
    edited_body: str | None = None,
    review_seconds: int | None = None,
    request_id: str | None = None,
    now: str | None = None,
) -> Review:
    """Approve the draft as it is, or with the reviewer's edit (recorded as `edit_approve`).

    The reviewer is the check on an edit: the draft checks are not run again on the new text
    (D-050). An edit that changes nothing but surrounding whitespace is a plain approval."""
    draft, inquiry = _draft_and_inquiry(conn, draft_id)
    _check_seconds(review_seconds)
    edit: str | None = None
    if edited_body is not None:
        text = edited_body.strip()
        if not text:
            raise InvalidReview("The edited reply is empty.")
        if len(text) > MAX_EDITED_CHARS or CONTROL_CHARACTERS.search(text):
            raise InvalidReview("The edited reply is too long or holds characters not allowed.")
        if text != draft.body.strip():
            edit = text
    with transaction(conn):
        _require_open_draft(conn, draft, inquiry)
        try:
            repo.set_draft_status(conn, draft.id, DraftStatus.approved)
        except repo.DraftBlocked:
            raise WrongState("This draft failed a blocking check and cannot be approved.") from None
        transition(conn, inquiry.id, S.approved, request_id=request_id, now=now)
        return _record(
            conn,
            inquiry.id,
            Decision.edit_approve if edit else Decision.approve,
            draft_id=draft.id,
            edited_body=edit,
            review_seconds=review_seconds,
            request_id=request_id,
            now=now,
        )


def reject(
    conn: sqlite3.Connection,
    draft_id: int,
    *,
    reason: str | None,
    review_seconds: int | None = None,
    request_id: str | None = None,
    now: str | None = None,
) -> Review:
    """Reject the draft. The inquiry waits as `rejected` for a redraft or for `resolve`."""
    draft, inquiry = _draft_and_inquiry(conn, draft_id)
    _check_seconds(review_seconds)
    why = _clean_note(reason, required=True, what="reason")
    with transaction(conn):
        _require_open_draft(conn, draft, inquiry)
        repo.set_draft_status(conn, draft.id, DraftStatus.rejected)
        transition(conn, inquiry.id, S.rejected, request_id=request_id, now=now)
        return _record(
            conn,
            inquiry.id,
            Decision.reject,
            draft_id=draft.id,
            reason=why,
            review_seconds=review_seconds,
            request_id=request_id,
            now=now,
        )


def escalate(
    conn: sqlite3.Connection,
    inquiry_id: int,
    *,
    note: str | None,
    request_id: str | None = None,
    now: str | None = None,
) -> Review:
    """Send an inquiry that is waiting for review to the owner's list (reason `MANUAL`).
    The draft stays where it is, to be shown "for reference"."""
    inquiry = _inquiry(conn, inquiry_id)
    why = _clean_note(note, required=True, what="note")
    with transaction(conn):
        if _inquiry(conn, inquiry_id).status is not S.needs_review:
            raise WrongState("Only an inquiry waiting for review can be escalated by hand.")
        draft = repo.latest_draft(conn, inquiry.id)
        repo.insert_escalation(
            conn,
            inquiry_id=inquiry.id,
            reason_code=ReasonCode.MANUAL,
            source=EscalationSource.reviewer,
            detail=MANUAL_DETAIL,
            now=now,
        )
        transition(conn, inquiry.id, S.escalated, request_id=request_id, now=now)
        return _record(
            conn,
            inquiry.id,
            Decision.escalate,
            draft_id=None if draft is None else draft.id,
            reason=why,
            request_id=request_id,
            now=now,
        )


def resolve(
    conn: sqlite3.Connection,
    inquiry_id: int,
    *,
    note: str | None,
    request_id: str | None = None,
    now: str | None = None,
) -> Review:
    """Close an escalated item handled outside the tool, or a rejected one with no reply."""
    inquiry = _inquiry(conn, inquiry_id)
    why = _clean_note(note, required=False, what="note")
    with transaction(conn):
        if _inquiry(conn, inquiry_id).status not in (S.escalated, S.rejected):
            raise WrongState("Only an escalated or rejected inquiry can be resolved.")
        draft = repo.latest_draft(conn, inquiry.id)
        repo.resolve_escalations(conn, inquiry.id, now=now)
        transition(conn, inquiry.id, S.resolved, request_id=request_id, now=now)
        return _record(
            conn,
            inquiry.id,
            Decision.resolve,
            draft_id=None if draft is None else draft.id,
            reason=why,
            request_id=request_id,
            now=now,
        )


def approved_text(conn: sqlite3.Connection, draft_id: int) -> ApprovedText:
    """The text the reviewer approved: their edit if there was one, otherwise the draft."""
    draft, inquiry = _draft_and_inquiry(conn, draft_id)
    if draft.status is not DraftStatus.approved or inquiry.status not in (S.approved, S.exported):
        raise WrongState("This draft has not been approved.")
    body = draft.body
    for recorded in repo.list_reviews(conn, inquiry.id):
        if recorded.draft_id == draft.id and recorded.edited_body:
            body = recorded.edited_body
    return ApprovedText(inquiry.id, draft.id, draft.subject, body)


def export(
    conn: sqlite3.Connection,
    draft_id: int,
    *,
    request_id: str | None = None,
    now: str | None = None,
) -> ApprovedText:
    """Record that the approved text was copied, and mark the inquiry `exported`.
    Copying again is allowed and recorded again. Nothing is sent."""
    with transaction(conn):
        text = approved_text(conn, draft_id)
        repo.insert_export(conn, draft_id=draft_id, method=ExportMethod.copy, now=now)
        if _inquiry(conn, text.inquiry_id).status is S.approved:
            transition(conn, text.inquiry_id, S.exported, request_id=request_id, now=now)
        return text
