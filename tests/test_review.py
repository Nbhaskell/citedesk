import sqlite3

import pytest

from citedesk import events, repo, review
from citedesk.db import connect, migrate
from citedesk.models import (
    AuditEventType,
    Decision,
    DraftStatus,
    EscalationSource,
    ExportMethod,
    InquiryStatus,
    ReasonCode,
)
from citedesk.review import InvalidReview, NotFound, WrongState
from tests.helpers import DRAFT_BODY, in_review

S = InquiryStatus
T2 = "2026-10-28T11:00:00Z"


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = connect(":memory:")
    migrate(c)
    return c


def status_of(conn: sqlite3.Connection, inquiry_id: int) -> S:
    inquiry = repo.get_inquiry(conn, inquiry_id)
    assert inquiry is not None
    return inquiry.status


def draft_status(conn: sqlite3.Connection, draft_id: int) -> DraftStatus:
    draft = repo.get_draft(conn, draft_id)
    assert draft is not None
    return draft.status


# --- approve ---------------------------------------------------------------------------------


def test_approve_marks_the_draft_and_the_inquiry_and_records_the_review(
    conn: sqlite3.Connection,
) -> None:
    inquiry_id, draft_id = in_review(conn)
    result = review.approve(conn, draft_id, review_seconds=42, now=T2)
    assert (status_of(conn, inquiry_id), draft_status(conn, draft_id)) == (
        S.approved,
        DraftStatus.approved,
    )
    [recorded] = repo.list_reviews(conn, inquiry_id)
    assert (recorded.decision, recorded.edited_body, recorded.review_seconds) == (
        Decision.approve,
        None,
        42,
    )
    assert recorded.draft_id == draft_id and result.id == recorded.id


def test_an_edit_is_saved_and_counted_as_an_edit(conn: sqlite3.Connection) -> None:
    inquiry_id, draft_id = in_review(conn)
    edited = DRAFT_BODY.replace("$175", "$175 plus tax")
    review.approve(conn, draft_id, edited_body=edited, now=T2)
    [recorded] = repo.list_reviews(conn, inquiry_id)
    assert (recorded.decision, recorded.edited_body) == (Decision.edit_approve, edited)


def test_an_edit_that_changes_nothing_is_a_plain_approval(conn: sqlite3.Connection) -> None:
    inquiry_id, draft_id = in_review(conn)
    review.approve(conn, draft_id, edited_body=DRAFT_BODY + "\n", now=T2)
    [recorded] = repo.list_reviews(conn, inquiry_id)
    assert (recorded.decision, recorded.edited_body) == (Decision.approve, None)


@pytest.mark.parametrize("edited", ["", "   \n ", "x" * (review.MAX_EDITED_CHARS + 1)])
def test_an_empty_or_huge_edit_is_refused_and_nothing_changes(
    conn: sqlite3.Connection, edited: str
) -> None:
    inquiry_id, draft_id = in_review(conn)
    with pytest.raises(InvalidReview):
        review.approve(conn, draft_id, edited_body=edited, now=T2)
    assert status_of(conn, inquiry_id) is S.needs_review
    assert repo.list_reviews(conn, inquiry_id) == []


def test_a_blocked_draft_cannot_be_approved(conn: sqlite3.Connection) -> None:
    inquiry_id, draft_id = in_review(conn, blocked=True)
    with pytest.raises(WrongState):
        review.approve(conn, draft_id, now=T2)
    assert status_of(conn, inquiry_id) is S.escalated
    assert draft_status(conn, draft_id) is DraftStatus.blocked


def test_approving_twice_is_refused(conn: sqlite3.Connection) -> None:
    inquiry_id, draft_id = in_review(conn)
    review.approve(conn, draft_id, now=T2)
    with pytest.raises(WrongState):
        review.approve(conn, draft_id, now=T2)
    assert len(repo.list_reviews(conn, inquiry_id)) == 1


def test_an_older_draft_version_cannot_be_approved(conn: sqlite3.Connection) -> None:
    inquiry_id, old_id = in_review(conn)
    newer = repo.insert_draft(
        conn, inquiry_id=inquiry_id, kind="reply", body="Hello,\n\nNew.\n\nKind regards,\nB",
        model="fake", prompt_version="draft-v1", now=T2,
    )  # fmt: skip
    repo.set_draft_status(conn, old_id, DraftStatus.superseded)
    repo.set_draft_status(conn, newer, DraftStatus.ready)
    with pytest.raises(WrongState):
        review.approve(conn, old_id, now=T2)


def test_an_unknown_draft_is_not_found(conn: sqlite3.Connection) -> None:
    with pytest.raises(NotFound):
        review.approve(conn, 999, now=T2)


@pytest.mark.parametrize("seconds", [-1, 86_401])
def test_review_seconds_out_of_range_is_refused(conn: sqlite3.Connection, seconds: int) -> None:
    _, draft_id = in_review(conn)
    with pytest.raises(InvalidReview):
        review.approve(conn, draft_id, review_seconds=seconds, now=T2)


def test_approval_writes_an_audit_event_with_codes_only(conn: sqlite3.Connection) -> None:
    inquiry_id, draft_id = in_review(conn)
    review.approve(conn, draft_id, edited_body="Hello,\n\nChanged.\n\nKind regards,\nB", now=T2)
    [event] = [
        e
        for e in events.list_events(conn, inquiry_id)
        if e.event_type is AuditEventType.review_recorded
    ]
    assert event.payload == {"decision": "edit_approve", "draft_id": draft_id}
    assert "Changed" not in str(event.payload)


# --- reject, close, redraft ------------------------------------------------------------------


def test_reject_needs_a_reason(conn: sqlite3.Connection) -> None:
    inquiry_id, draft_id = in_review(conn)
    for reason in ("", "   "):
        with pytest.raises(InvalidReview):
            review.reject(conn, draft_id, reason=reason, now=T2)
    assert status_of(conn, inquiry_id) is S.needs_review


def test_reject_marks_the_draft_and_keeps_the_reason_in_the_review_only(
    conn: sqlite3.Connection,
) -> None:
    inquiry_id, draft_id = in_review(conn)
    review.reject(conn, draft_id, reason="Price is out of date", now=T2)
    assert (status_of(conn, inquiry_id), draft_status(conn, draft_id)) == (
        S.rejected,
        DraftStatus.rejected,
    )
    [recorded] = repo.list_reviews(conn, inquiry_id)
    assert (recorded.decision, recorded.reason) == (Decision.reject, "Price is out of date")
    assert all("out of date" not in str(e.payload) for e in events.list_events(conn, inquiry_id))


def test_a_rejected_inquiry_can_be_closed_without_a_reply(conn: sqlite3.Connection) -> None:
    inquiry_id, draft_id = in_review(conn)
    review.reject(conn, draft_id, reason="Not worth a reply", now=T2)
    review.resolve(conn, inquiry_id, note=None, now=T2)
    assert status_of(conn, inquiry_id) is S.resolved
    assert [r.decision for r in repo.list_reviews(conn, inquiry_id)] == [
        Decision.reject,
        Decision.resolve,
    ]


# --- escalate --------------------------------------------------------------------------------


def test_escalate_needs_a_note(conn: sqlite3.Connection) -> None:
    inquiry_id, _ = in_review(conn)
    with pytest.raises(InvalidReview):
        review.escalate(conn, inquiry_id, note=" ", now=T2)
    assert status_of(conn, inquiry_id) is S.needs_review


def test_escalate_records_a_manual_reason_and_leaves_the_draft_for_reference(
    conn: sqlite3.Connection,
) -> None:
    inquiry_id, draft_id = in_review(conn)
    review.escalate(conn, inquiry_id, note="Owner should see this", now=T2)
    assert status_of(conn, inquiry_id) is S.escalated
    [escalation] = repo.list_escalations(conn, inquiry_id)
    assert (escalation.reason_code, escalation.source) == (
        ReasonCode.MANUAL,
        EscalationSource.reviewer,
    )
    assert "Owner should see this" not in (escalation.detail or "")
    [recorded] = repo.list_reviews(conn, inquiry_id)
    assert (recorded.decision, recorded.reason) == (Decision.escalate, "Owner should see this")
    assert draft_status(conn, draft_id) is DraftStatus.ready


def test_only_an_inquiry_in_review_can_be_escalated_by_hand(conn: sqlite3.Connection) -> None:
    inquiry_id, _ = in_review(conn, blocked=True)
    with pytest.raises(WrongState):
        review.escalate(conn, inquiry_id, note="Look at this", now=T2)


# --- resolve ---------------------------------------------------------------------------------


def test_resolve_closes_an_escalation_and_its_open_reasons(conn: sqlite3.Connection) -> None:
    inquiry_id, _ = in_review(conn)
    review.escalate(conn, inquiry_id, note="Needs the owner", now=T2)
    review.resolve(conn, inquiry_id, note="Phoned the customer", now=T2)
    assert status_of(conn, inquiry_id) is S.resolved
    assert repo.list_escalations(conn, inquiry_id, open_only=True) == []
    assert repo.list_reviews(conn, inquiry_id)[-1].reason == "Phoned the customer"


def test_resolve_works_on_an_item_escalated_by_the_pipeline(conn: sqlite3.Connection) -> None:
    inquiry_id, _ = in_review(conn, blocked=True)
    review.resolve(conn, inquiry_id, note=None, now=T2)
    assert status_of(conn, inquiry_id) is S.resolved


@pytest.mark.parametrize("target", [S.needs_review, S.approved])
def test_resolve_is_refused_from_other_states(conn: sqlite3.Connection, target: S) -> None:
    inquiry_id, draft_id = in_review(conn)
    if target is S.approved:
        review.approve(conn, draft_id, now=T2)
    with pytest.raises(WrongState):
        review.resolve(conn, inquiry_id, note=None, now=T2)


# --- export ----------------------------------------------------------------------------------


def test_the_approved_text_is_the_draft_or_the_edit(conn: sqlite3.Connection) -> None:
    _, plain = in_review(conn)
    review.approve(conn, plain, now=T2)
    assert review.approved_text(conn, plain).body == DRAFT_BODY
    _, edited = in_review(conn)
    review.approve(conn, edited, edited_body="Hello,\n\nChanged.\n\nKind regards,\nB", now=T2)
    assert review.approved_text(conn, edited).body == "Hello,\n\nChanged.\n\nKind regards,\nB"


def test_the_text_of_a_draft_that_is_not_approved_is_not_available(
    conn: sqlite3.Connection,
) -> None:
    _, draft_id = in_review(conn)
    with pytest.raises(WrongState):
        review.approved_text(conn, draft_id)


def test_export_records_a_copy_and_moves_to_exported_once(conn: sqlite3.Connection) -> None:
    inquiry_id, draft_id = in_review(conn)
    review.approve(conn, draft_id, now=T2)
    review.export(conn, draft_id, now=T2)
    review.export(conn, draft_id, now=T2)
    assert status_of(conn, inquiry_id) is S.exported
    assert [e.method for e in repo.list_exports(conn, draft_id)] == [ExportMethod.copy] * 2


def test_export_before_approval_is_refused(conn: sqlite3.Connection) -> None:
    _, draft_id = in_review(conn)
    with pytest.raises(WrongState):
        review.export(conn, draft_id, now=T2)
    assert repo.list_exports(conn, draft_id) == []
