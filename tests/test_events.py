import math
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from citedesk import events, repo
from citedesk.db import connect, migrate
from citedesk.events import PayloadRejected, record_event, validate_payload
from citedesk.models import AuditEventType, InquiryStatus, Stage

REPO_ROOT = Path(__file__).resolve().parent.parent
T1 = "2026-10-28T10:00:00Z"


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = connect(":memory:")
    migrate(c)
    return c


def new_inquiry(conn: sqlite3.Connection, **over: Any) -> int:
    args: dict[str, Any] = {"channel": "web_form", "body": "How much for a drain?", "now": T1}
    return repo.insert_inquiry(conn, **{**args, **over})


# --- what a payload may hold -----------------------------------------------------------------


def test_the_documented_examples_are_accepted() -> None:
    validate_payload({"route": "escalate", "reason_codes": ["HEALTH_SAFETY"], "safety_net": True})
    validate_payload({"check": "FIGURES_GROUNDED", "passed": False})


def test_numbers_booleans_null_and_versions_are_accepted() -> None:
    validate_payload(
        {
            "count": 3,
            "ratio": 0.25,
            "flag": False,
            "nothing": None,
            "prompt_version": "understand-v1",
            "model": "qwen3:8b",
            "ids": [1, 2, 3],
            "codes": ["a_code", "B-2"],
        }
    )


def test_an_empty_payload_is_fine() -> None:
    assert validate_payload({}) == {}


def test_the_returned_payload_is_a_copy() -> None:
    original = {"ids": [1]}
    result = validate_payload(original)
    result["ids"].append(2)
    assert original == {"ids": [1]}


@pytest.mark.parametrize(
    "text",
    [
        "How much for a drain?",
        "my dog is called Biscuit",
        "two words",
        "line one\nline two",
        "tab\tseparated",
        "x" * 65,
        "alex.rivera@example.com",
        "http://example.com/a",
        "see https://example.com",
        "5550142",
        "555-0142 call me",
        "",
        " leading",
        "trailing ",
        "naïve",
    ],
)
def test_message_like_strings_are_rejected(text: str) -> None:
    with pytest.raises(PayloadRejected):
        validate_payload({"detail": text})


def test_a_sentence_inside_a_list_is_rejected() -> None:
    with pytest.raises(PayloadRejected):
        validate_payload({"flags": ["fine_code", "this is a sentence"]})


@pytest.mark.parametrize(
    "payload",
    [
        {"nested": {"a": 1}},
        {"nested": [[1, 2]]},
        {"nested": [{"a": 1}]},
        {"too_long": list(range(51))},
        {"value": object()},
        {"value": b"bytes"},
        {"value": {1, 2}},
        {"value": float("nan")},
        {"value": math.inf},
        {"value": (1, 2)},
    ],
)
def test_other_shapes_are_rejected(payload: dict[str, Any]) -> None:
    with pytest.raises(PayloadRejected):
        validate_payload(payload)


@pytest.mark.parametrize(
    "key", ["Has Space", "UPPER", "with-dash", "1leading", "", "k" * 42, "naïve"]
)
def test_keys_must_be_plain_snake_case_names(key: str) -> None:
    with pytest.raises(PayloadRejected):
        validate_payload({key: 1})


def test_non_string_keys_are_rejected() -> None:
    with pytest.raises(PayloadRejected):
        validate_payload({1: "a"})  # type: ignore[dict-item]


def test_a_huge_payload_is_rejected() -> None:
    payload = {f"key_{i}": "value" for i in range(200)}
    with pytest.raises(PayloadRejected, match="large"):
        validate_payload(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"detail": "Customer says the toilet is leaking badly"},
        {"detail": ["fine", "Customer says the toilet is leaking badly"]},
        {"Bad Key With Words": 1},
    ],
)
def test_a_rejection_never_repeats_the_rejected_text(payload: dict[str, Any]) -> None:
    """The exception message may be logged, so it must not carry what was rejected."""
    with pytest.raises(PayloadRejected) as caught:
        validate_payload(payload)
    message = str(caught.value).lower()
    assert "toilet" not in message and "leaking" not in message and "bad key" not in message


# --- a single word copied from the message ---------------------------------------------------


def test_a_word_from_the_message_is_rejected() -> None:
    with pytest.raises(PayloadRejected, match="message"):
        validate_payload({"note": "biscuit"}, protect=["my dog is called Biscuit"])


def test_the_check_is_case_insensitive_and_whole_word() -> None:
    with pytest.raises(PayloadRejected):
        validate_payload({"note": "BISCUIT"}, protect=["my dog is called Biscuit"])
    validate_payload({"note": "bisc"}, protect=["my dog is called Biscuit"])


def test_words_from_a_list_value_are_checked_too() -> None:
    with pytest.raises(PayloadRejected):
        validate_payload({"words": ["fine", "rivera"]}, protect=["Alex Rivera"])


def test_known_codes_are_allowed_even_if_the_customer_used_the_word() -> None:
    validate_payload({"urgency": "urgent"}, protect=["this is urgent!!"])
    validate_payload({"reason": "COMPLAINT"}, protect=["COMPLAINT about your tech"])
    validate_payload({"intent": "spam", "route": "archive"}, protect=["spam archive"])


def test_every_screening_pattern_and_signal_name_is_a_known_code() -> None:
    from citedesk.safety import EMERGENCY_PATTERNS
    from citedesk.screening import DERIVED_FLAGS, SPAM_SIGNALS, STRONG, WEAK

    names = [*EMERGENCY_PATTERNS, *STRONG, *WEAK, *SPAM_SIGNALS, *DERIVED_FLAGS]
    assert "sewage" in names and "links" in names
    for name in names:
        validate_payload({"value": name}, protect=[f"the customer wrote {name} here"])


def test_every_stage_and_status_name_is_a_known_code() -> None:
    for name in [*(s.value for s in Stage), *(s.value for s in InquiryStatus)]:
        validate_payload({"value": name}, protect=[name])


# --- recording events ------------------------------------------------------------------------


def test_record_event_writes_a_readable_row(conn: sqlite3.Connection) -> None:
    inquiry_id = new_inquiry(conn)
    event_id = record_event(
        conn,
        event_type=AuditEventType.route_decided,
        inquiry_id=inquiry_id,
        stage=Stage.route,
        payload={"route": "escalate", "reason_codes": ["HEALTH_SAFETY"]},
        request_id="req-1",
        duration_ms=12,
        now=T1,
    )
    [event] = events.list_events(conn, inquiry_id)
    assert event.id == event_id
    assert event.event_type is AuditEventType.route_decided
    assert event.stage is Stage.route
    assert event.payload == {"route": "escalate", "reason_codes": ["HEALTH_SAFETY"]}
    assert (event.request_id, event.duration_ms, event.created_at) == ("req-1", 12, T1)


def test_status_changes_carry_both_statuses(conn: sqlite3.Connection) -> None:
    inquiry_id = new_inquiry(conn)
    record_event(
        conn,
        event_type="status_changed",
        inquiry_id=inquiry_id,
        from_status=InquiryStatus.received,
        to_status=InquiryStatus.screened,
    )
    [event] = events.list_events(conn, inquiry_id)
    assert (event.from_status, event.to_status) == (InquiryStatus.received, InquiryStatus.screened)
    assert event.payload == {}


def test_events_without_an_inquiry_are_allowed(conn: sqlite3.Connection) -> None:
    record_event(conn, event_type=AuditEventType.stage_failed, payload={"stage": "draft"})
    row = conn.execute("SELECT inquiry_id FROM audit_events").fetchone()
    assert row["inquiry_id"] is None


def test_a_rejected_payload_writes_nothing(conn: sqlite3.Connection) -> None:
    inquiry_id = new_inquiry(conn)
    with pytest.raises(PayloadRejected):
        record_event(
            conn,
            event_type=AuditEventType.stage_failed,
            inquiry_id=inquiry_id,
            payload={"error": "Customer wrote: how much for a drain"},
        )
    assert conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0] == 0


def test_a_word_from_this_inquiry_is_rejected_but_not_from_another(
    conn: sqlite3.Connection,
) -> None:
    mine = new_inquiry(conn, body="my cat is called Whiskers", sender_name="Alex Rivera")
    other = new_inquiry(conn, body="how much for a drain")
    with pytest.raises(PayloadRejected):
        record_event(conn, event_type="stage_failed", inquiry_id=mine, payload={"note": "whiskers"})
    with pytest.raises(PayloadRejected):
        record_event(conn, event_type="stage_failed", inquiry_id=mine, payload={"note": "Rivera"})
    record_event(conn, event_type="stage_failed", inquiry_id=other, payload={"note": "whiskers"})


def test_the_subject_and_email_of_the_inquiry_are_protected(conn: sqlite3.Connection) -> None:
    inquiry_id = new_inquiry(conn, subject="Boarding", sender_email="alex.rivera@example.com")
    with pytest.raises(PayloadRejected):
        record_event(
            conn, event_type="stage_failed", inquiry_id=inquiry_id, payload={"n": "boarding"}
        )


def test_unknown_event_types_are_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValueError):
        record_event(conn, event_type="something_else")


def test_an_unknown_inquiry_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        record_event(conn, event_type="stage_started", inquiry_id=999)


def test_list_events_is_in_order_and_per_inquiry(conn: sqlite3.Connection) -> None:
    a, b = new_inquiry(conn), new_inquiry(conn)
    record_event(
        conn, event_type="stage_started", inquiry_id=a, stage="screen", now="2026-10-28T10:00:01Z"
    )
    record_event(
        conn, event_type="stage_started", inquiry_id=b, stage="screen", now="2026-10-28T10:00:02Z"
    )
    record_event(
        conn, event_type="stage_finished", inquiry_id=a, stage="screen", now="2026-10-28T10:00:03Z"
    )
    assert [e.event_type for e in events.list_events(conn, a)] == [
        AuditEventType.stage_started,
        AuditEventType.stage_finished,
    ]
    assert len(events.list_events(conn, b)) == 1


# --- nothing bypasses the filter -------------------------------------------------------------


def test_only_the_events_module_writes_to_the_audit_table() -> None:
    offenders = []
    for path in (REPO_ROOT / "citedesk").glob("*.py"):
        if path.name == "events.py":
            continue
        text = path.read_text("utf-8").lower()
        if "insert into audit_events" in text or "into audit_events" in text:
            offenders.append(path.name)
    assert offenders == []
