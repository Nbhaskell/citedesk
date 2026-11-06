"""The focused signals are stored with the classification and read back by the route stage (D-075).

The first version kept only the main reading's signals (D-041 reads them from the stored reply),
so a signal raised by the focused call was computed and then lost before routing. These tests fail
if that happens again.
"""

import json
import sqlite3
from typing import Any

import pytest

from citedesk import pipeline, repo
from citedesk.config import Settings
from citedesk.db import connect, migrate
from citedesk.intake import NewInquiry, submit
from citedesk.models import InquiryStatus, ReasonCode
from citedesk.providers import FakeLLM
from tests.helpers import model_reply
from tests.test_repo import classify, new_inquiry

NOW = "2026-10-28T12:00:00Z"
R = ReasonCode


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = connect(":memory:")
    migrate(c)
    return c


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)


def stage(
    conn: sqlite3.Connection, settings: Settings, llm: FakeLLM, **inquiry: Any
) -> tuple[int, InquiryStatus]:
    body = {"sender_name": "A", "subject": "Rates", "body": "Is there a landlord rate?"}
    new = NewInquiry.model_validate({**body, **inquiry, "received_at": NOW})
    inquiry_id = submit(conn, new, settings, now=NOW).id
    pipeline.screen_stage(conn, inquiry_id, settings, now=NOW)
    pipeline.understand_stage(conn, inquiry_id, settings, llm, now=NOW)
    return inquiry_id, pipeline.route_stage(conn, inquiry_id, settings, now=NOW)


def test_the_classification_table_has_a_focused_signals_column(conn: sqlite3.Connection) -> None:
    columns = {row["name"]: row for row in conn.execute("PRAGMA table_info(classifications)")}
    assert columns["focused_signals"]["notnull"] == 1
    assert columns["focused_signals"]["dflt_value"] == "'[]'"


def test_a_classification_stores_and_returns_its_focused_signals(
    conn: sqlite3.Connection,
) -> None:
    inquiry_id = new_inquiry(conn)
    classify(conn, inquiry_id, focused_signals=[R.INJECTION_SUSPECTED, R.POLICY_EXCEPTION_REQUEST])
    found = repo.latest_classification(conn, inquiry_id)
    assert found is not None
    assert found.focused_signals == [R.INJECTION_SUSPECTED, R.POLICY_EXCEPTION_REQUEST]


def test_a_classification_without_focused_signals_has_an_empty_list(
    conn: sqlite3.Connection,
) -> None:
    inquiry_id = new_inquiry(conn)
    classify(conn, inquiry_id)
    found = repo.latest_classification(conn, inquiry_id)
    assert found is not None and found.focused_signals == []


def test_an_injection_flag_from_the_focused_call_escalates_the_inquiry(
    conn: sqlite3.Connection, settings: Settings
) -> None:
    llm = FakeLLM([model_reply()], addresses_assistant=True)
    inquiry_id, status = stage(conn, settings, llm)
    assert status is InquiryStatus.escalated
    reasons = {e.reason_code for e in repo.list_escalations(conn, inquiry_id)}
    assert reasons == {R.INJECTION_SUSPECTED}


def test_an_exception_flag_from_the_focused_call_escalates_the_inquiry(
    conn: sqlite3.Connection, settings: Settings
) -> None:
    llm = FakeLLM([model_reply()], asks_exception=True)
    inquiry_id, status = stage(conn, settings, llm)
    assert status is InquiryStatus.escalated
    reasons = {e.reason_code for e in repo.list_escalations(conn, inquiry_id)}
    assert reasons == {R.POLICY_EXCEPTION_REQUEST}


def test_no_flag_from_either_call_leaves_the_inquiry_on_the_draft_path(
    conn: sqlite3.Connection, settings: Settings
) -> None:
    _, status = stage(conn, settings, FakeLLM([model_reply()]))
    assert status is InquiryStatus.routed


def test_the_stored_reply_is_still_exactly_what_the_main_reading_said(
    conn: sqlite3.Connection, settings: Settings
) -> None:
    llm = FakeLLM([model_reply()], addresses_assistant=True)
    inquiry_id, _ = stage(conn, settings, llm)
    stored = repo.latest_classification(conn, inquiry_id)
    assert stored is not None
    assert json.loads(stored.raw_response)["escalation_signals"] == []
    assert stored.focused_signals == [R.INJECTION_SUSPECTED]


def test_a_flag_the_main_reading_raised_is_not_stored_as_a_focused_one(
    conn: sqlite3.Connection, settings: Settings
) -> None:
    llm = FakeLLM(
        [model_reply(escalation_signals=["POLICY_EXCEPTION_REQUEST"])], asks_exception=True
    )
    inquiry_id, _ = stage(conn, settings, llm)
    stored = repo.latest_classification(conn, inquiry_id)
    assert stored is not None and stored.focused_signals == []
    reasons = [e.reason_code for e in repo.list_escalations(conn, inquiry_id)]
    assert reasons == [R.POLICY_EXCEPTION_REQUEST]
