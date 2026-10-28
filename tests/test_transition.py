import sqlite3
from pathlib import Path
from typing import Any

import pytest

from citedesk import events, repo, state
from citedesk.db import connect, migrate
from citedesk.events import PayloadRejected
from citedesk.models import AuditEventType, InquiryStatus, Stage
from citedesk.state import InvalidTransition, transition

REPO_ROOT = Path(__file__).resolve().parent.parent
S = InquiryStatus
T1, T2, T3 = "2026-10-28T10:00:00Z", "2026-10-28T11:00:00Z", "2026-10-28T12:00:00Z"


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = connect(":memory:")
    migrate(c)
    return c


def new_inquiry(conn: sqlite3.Connection, **over: Any) -> int:
    args: dict[str, Any] = {"channel": "web_form", "body": "How much for a drain?", "now": T1}
    return repo.insert_inquiry(conn, **{**args, **over})


def status_of(conn: sqlite3.Connection, inquiry_id: int) -> S:
    inquiry = repo.get_inquiry(conn, inquiry_id)
    assert inquiry is not None
    return inquiry.status


def walk(conn: sqlite3.Connection, inquiry_id: int, *path: S) -> None:
    for step in path:
        transition(conn, inquiry_id, step, now=T1)


# --- the happy path --------------------------------------------------------------------------


def test_the_full_path_to_export_updates_status_and_writes_one_event_per_step(
    conn: sqlite3.Connection,
) -> None:
    inquiry_id = new_inquiry(conn)
    path = [S.screened, S.classified, S.routed, S.drafted, S.needs_review, S.approved, S.exported]
    for step in path:
        transition(conn, inquiry_id, step, now=T2)
    assert status_of(conn, inquiry_id) is S.exported
    logged = events.list_events(conn, inquiry_id)
    assert [e.event_type for e in logged] == [AuditEventType.status_changed] * len(path)
    assert [e.to_status for e in logged] == path
    assert [e.from_status for e in logged] == [S.received, *path[:-1]]


def test_a_transition_bumps_updated_at_only(conn: sqlite3.Connection) -> None:
    inquiry_id = new_inquiry(conn)
    transition(conn, inquiry_id, S.screened, now=T2)
    inquiry = repo.get_inquiry(conn, inquiry_id)
    assert inquiry is not None
    assert (inquiry.created_at, inquiry.updated_at) == (T1, T2)


def test_stage_request_id_and_duration_are_recorded(conn: sqlite3.Connection) -> None:
    inquiry_id = new_inquiry(conn)
    transition(
        conn, inquiry_id, S.screened, stage=Stage.screen, request_id="req-7", duration_ms=31, now=T2
    )
    [event] = events.list_events(conn, inquiry_id)
    assert (event.stage, event.request_id, event.duration_ms) == (Stage.screen, "req-7", 31)


def test_other_branches_are_reachable(conn: sqlite3.Connection) -> None:
    spam, risky, review = new_inquiry(conn), new_inquiry(conn), new_inquiry(conn)
    walk(conn, spam, S.screened, S.archived)
    walk(conn, risky, S.screened, S.escalated, S.resolved)
    walk(
        conn,
        review,
        S.screened,
        S.classified,
        S.routed,
        S.drafted,
        S.needs_review,
        S.rejected,
        S.drafted,
    )
    assert status_of(conn, spam) is S.archived
    assert status_of(conn, risky) is S.resolved
    assert status_of(conn, review) is S.drafted


# --- refusals --------------------------------------------------------------------------------


def test_an_invalid_move_changes_nothing(conn: sqlite3.Connection) -> None:
    inquiry_id = new_inquiry(conn)
    with pytest.raises(InvalidTransition):
        transition(conn, inquiry_id, S.approved, now=T2)
    inquiry = repo.get_inquiry(conn, inquiry_id)
    assert inquiry is not None
    assert (inquiry.status, inquiry.updated_at) == (S.received, T1)
    assert events.list_events(conn, inquiry_id) == []


def test_a_reviewer_cannot_approve_something_that_never_reached_review(
    conn: sqlite3.Connection,
) -> None:
    inquiry_id = new_inquiry(conn)
    walk(conn, inquiry_id, S.screened, S.classified, S.routed, S.drafted)
    with pytest.raises(InvalidTransition):
        transition(conn, inquiry_id, S.approved)
    assert status_of(conn, inquiry_id) is S.drafted


def test_a_missing_inquiry_is_an_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(LookupError):
        transition(conn, 999, S.screened)


def test_a_failure_to_write_the_audit_event_undoes_the_status_change(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    inquiry_id = new_inquiry(conn)

    def boom(*args: Any, **kwargs: Any) -> int:
        raise PayloadRejected("simulated")

    monkeypatch.setattr(state, "record_event", boom)
    with pytest.raises(PayloadRejected):
        transition(conn, inquiry_id, S.screened, now=T2)
    assert status_of(conn, inquiry_id) is S.received
    assert not conn.in_transaction


def test_only_the_state_machine_writes_inquiry_status() -> None:
    offenders = []
    for path in (REPO_ROOT / "citedesk").glob("*.py"):
        if path.name == "state.py":
            continue
        if "update inquiries set status" in path.read_text("utf-8").lower():
            offenders.append(path.name)
    assert offenders == []


# --- failing ---------------------------------------------------------------------------------


def test_an_inquiry_can_fail_at_its_own_stage(conn: sqlite3.Connection) -> None:
    inquiry_id = new_inquiry(conn)
    walk(conn, inquiry_id, S.screened)
    transition(
        conn,
        inquiry_id,
        S.failed,
        failure_stage=Stage.understand,
        failure_message="Model returned invalid JSON twice",
        now=T2,
    )
    inquiry = repo.get_inquiry(conn, inquiry_id)
    assert inquiry is not None
    assert inquiry.status is S.failed
    assert inquiry.failure_stage is Stage.understand
    assert inquiry.failure_message == "Model returned invalid JSON twice"
    last = events.list_events(conn, inquiry_id)[-1]
    assert last.to_status is S.failed and last.payload == {"failure_stage": "understand"}


@pytest.mark.parametrize(
    ("path", "bad_stage"),
    [
        ([], Stage.draft),
        ([S.screened], Stage.screen),
        ([S.screened, S.classified], Stage.understand),
        ([S.screened, S.classified, S.routed], Stage.understand),
        ([S.screened, S.classified, S.routed], Stage.route),
    ],
)
def test_the_failed_stage_must_fit_the_current_status(
    conn: sqlite3.Connection, path: list[S], bad_stage: Stage
) -> None:
    inquiry_id = new_inquiry(conn)
    walk(conn, inquiry_id, *path)
    before = status_of(conn, inquiry_id)
    with pytest.raises(InvalidTransition):
        transition(conn, inquiry_id, S.failed, failure_stage=bad_stage, failure_message="x")
    assert status_of(conn, inquiry_id) is before


def test_a_crash_in_the_route_stage_can_be_recorded_from_classified(
    conn: sqlite3.Connection,
) -> None:
    inquiry_id = new_inquiry(conn)
    walk(conn, inquiry_id, S.screened, S.classified)
    transition(
        conn, inquiry_id, S.failed, failure_stage=Stage.route, failure_message="Routing crashed"
    )
    inquiry = repo.get_inquiry(conn, inquiry_id)
    assert inquiry is not None
    assert inquiry.status is S.failed and inquiry.failure_stage is Stage.route


def test_a_crash_in_the_check_stage_can_be_recorded_from_drafted(conn: sqlite3.Connection) -> None:
    inquiry_id = new_inquiry(conn)
    walk(conn, inquiry_id, S.screened, S.classified, S.routed, S.drafted)
    transition(
        conn, inquiry_id, S.failed, failure_stage=Stage.check, failure_message="Checking crashed"
    )
    assert status_of(conn, inquiry_id) is S.failed


def test_statuses_that_cannot_fail_refuse_to(conn: sqlite3.Connection) -> None:
    # Once a draft is waiting for a person there is no stage left that can fail.
    inquiry_id = new_inquiry(conn)
    walk(conn, inquiry_id, S.screened, S.classified, S.routed, S.drafted, S.needs_review)
    with pytest.raises(InvalidTransition):
        transition(conn, inquiry_id, S.failed, failure_stage=Stage.check, failure_message="x")


def test_failing_needs_a_stage_and_a_short_message(conn: sqlite3.Connection) -> None:
    inquiry_id = new_inquiry(conn)
    with pytest.raises(ValueError, match="failure_stage"):
        transition(conn, inquiry_id, S.failed, failure_message="x")
    with pytest.raises(ValueError, match="failure_message"):
        transition(conn, inquiry_id, S.failed, failure_stage=Stage.screen)
    with pytest.raises(ValueError, match="failure_message"):
        transition(
            conn, inquiry_id, S.failed, failure_stage=Stage.screen, failure_message="x" * 301
        )
    assert status_of(conn, inquiry_id) is S.received


def test_a_failure_message_may_not_quote_the_customer(conn: sqlite3.Connection) -> None:
    inquiry_id = new_inquiry(
        conn,
        body="Please can someone come and look at my leaking water heater today",
        subject="Leaking heater",
    )
    with pytest.raises(ValueError, match="message text"):
        transition(
            conn,
            inquiry_id,
            S.failed,
            failure_stage=Stage.screen,
            failure_message=(
                "Crashed on: Please can someone come and look at my leaking water heater today"
            ),
        )
    with pytest.raises(ValueError, match="message text"):
        transition(
            conn,
            inquiry_id,
            S.failed,
            failure_stage=Stage.screen,
            failure_message="Bad input: someone come and look at my leaking water",
        )
    transition(
        conn,
        inquiry_id,
        S.failed,
        failure_stage=Stage.screen,
        failure_message="Screening crashed twice",
    )
    assert status_of(conn, inquiry_id) is S.failed


def test_failure_details_are_refused_on_a_non_failing_move(conn: sqlite3.Connection) -> None:
    inquiry_id = new_inquiry(conn)
    with pytest.raises(ValueError, match="only"):
        transition(conn, inquiry_id, S.screened, failure_stage=Stage.screen, failure_message="x")


# --- retrying --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "stage", "back_to"),
    [
        ([], Stage.screen, S.received),
        ([S.screened], Stage.understand, S.screened),
        ([S.screened, S.classified], Stage.route, S.classified),
        ([S.screened, S.classified, S.routed], Stage.retrieve, S.routed),
        ([S.screened, S.classified, S.routed], Stage.draft, S.routed),
        ([S.screened, S.classified, S.routed, S.drafted], Stage.check, S.drafted),
    ],
)
def test_retry_returns_to_where_the_failed_stage_started_and_clears_the_failure(
    conn: sqlite3.Connection, path: list[S], stage: Stage, back_to: S
) -> None:
    inquiry_id = new_inquiry(conn)
    walk(conn, inquiry_id, *path)
    transition(conn, inquiry_id, S.failed, failure_stage=stage, failure_message="gave up", now=T2)
    transition(conn, inquiry_id, back_to, now=T3)
    inquiry = repo.get_inquiry(conn, inquiry_id)
    assert inquiry is not None
    assert inquiry.status is back_to
    assert inquiry.failure_stage is None and inquiry.failure_message is None
    last = events.list_events(conn, inquiry_id)[-1]
    assert (last.from_status, last.to_status) == (S.failed, back_to)
    assert last.payload == {"retry_of_stage": stage.value}


def test_retry_to_the_wrong_status_is_refused_and_the_failure_stays(
    conn: sqlite3.Connection,
) -> None:
    inquiry_id = new_inquiry(conn)
    walk(conn, inquiry_id, S.screened)
    transition(
        conn, inquiry_id, S.failed, failure_stage=Stage.understand, failure_message="gave up"
    )
    for wrong in (S.received, S.classified, S.routed, S.escalated, S.resolved):
        with pytest.raises(InvalidTransition):
            transition(conn, inquiry_id, wrong)
    inquiry = repo.get_inquiry(conn, inquiry_id)
    assert inquiry is not None
    assert inquiry.status is S.failed and inquiry.failure_stage is Stage.understand
