"""Phase 8: what happens when the model, the knowledge base or the database fails.

Each test follows one inquiry from a failure to its recovery. The things that must hold every time:
a received inquiry is never lost, the failure is named by stage and kind (never by text), a person
can retry it, and the retry carries on from where it stopped.
"""

import logging
import sqlite3
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from citedesk import db, pipeline
from citedesk.config import Settings
from citedesk.db import connect
from citedesk.intake import NewInquiry, submit
from citedesk.knowledge import FakeKB, KnowledgeBaseError
from citedesk.providers import FakeLLM
from citedesk.providers.base import LLMTimeout, LLMUnavailable
from tests.helpers import model_reply
from tests.test_api import assert_error, post
from tests.test_api_review import status_of, waiting
from tests.test_pipeline_drafting import BUSINESS, GOOD_DRAFT, answering


@contextmanager
def database(settings: Settings) -> Iterator[sqlite3.Connection]:
    conn = connect(settings.db_path)
    try:
        yield conn
    finally:
        conn.close()


def run(
    settings: Settings,
    inquiry_id: int,
    llm: FakeLLM,
    kb: FakeKB | None = None,
) -> str:
    with database(settings) as conn:
        return pipeline.process(
            conn, inquiry_id, settings, llm=llm, kb=kb, business=BUSINESS if kb else None
        ).value


def detail(client: TestClient, inquiry_id: int) -> dict[str, Any]:
    body: dict[str, Any] = client.get(f"/api/inquiries/{inquiry_id}").json()
    return body


def failed_at(client: TestClient, inquiry_id: int, stage: str) -> str:
    inquiry = detail(client, inquiry_id)["inquiry"]
    assert inquiry["status"] == "failed"
    assert inquiry["failure_stage"] == stage
    message = str(inquiry["failure_message"])
    assert "kitchen drain" not in message  # a reason, never the customer's words
    return message


def reprocess(client: TestClient, inquiry_id: int) -> str:
    response = client.post(f"/api/inquiries/{inquiry_id}/reprocess")
    assert response.status_code == 200, response.text
    assert response.json()["inquiry"]["failure_stage"] is None
    return str(response.json()["inquiry"]["status"])


# --- the model is offline or gives nothing usable --------------------------------------------


@pytest.mark.parametrize("error", [LLMUnavailable("x"), LLMTimeout("x")], ids=["offline", "slow"])
def test_a_model_that_is_offline_fails_the_inquiry_and_a_retry_recovers(
    client: TestClient, api_settings: Settings, error: Exception
) -> None:
    inquiry_id = post(client).json()["id"]
    assert run(api_settings, inquiry_id, FakeLLM([error, error])) == "failed"
    assert failed_at(client, inquiry_id, "understand").startswith("The model gave no usable reply")

    assert reprocess(client, inquiry_id) in {"received", "screened"}
    assert run(api_settings, inquiry_id, FakeLLM([model_reply(), GOOD_DRAFT]), answering()) in {
        "needs_review",
        "escalated",
    }
    assert len(client.get("/api/inquiries").json()["items"]) == 1
    assert status_of(client, inquiry_id) == "needs_review"


def test_invalid_json_twice_at_understanding_fails_at_that_stage_and_a_retry_recovers(
    client: TestClient, api_settings: Settings
) -> None:
    inquiry_id = post(client).json()["id"]
    assert run(api_settings, inquiry_id, FakeLLM(["not json", "still not json"])) == "failed"
    assert "invalid_json" in failed_at(client, inquiry_id, "understand")
    assert detail(client, inquiry_id)["draft"] is None  # nothing was drafted from nothing

    reprocess(client, inquiry_id)
    assert run(api_settings, inquiry_id, FakeLLM([model_reply(), GOOD_DRAFT]), answering()) in {
        "needs_review",
        "escalated",
    }


def test_invalid_json_twice_while_drafting_fails_at_the_draft_stage_without_asking_again(
    client: TestClient, api_settings: Settings
) -> None:
    inquiry_id = post(client).json()["id"]
    llm = FakeLLM([model_reply(), "not json", "still not json"])
    assert run(api_settings, inquiry_id, llm, answering()) == "failed"
    assert "invalid_json" in failed_at(client, inquiry_id, "draft")
    assert detail(client, inquiry_id)["draft"] is None

    reprocess(client, inquiry_id)
    retry = FakeLLM([GOOD_DRAFT])  # the reading and retrieval are kept; only the draft is redone
    assert run(api_settings, inquiry_id, retry, FakeKB([])) == "needs_review"
    assert len(retry.calls) == 1


# --- the knowledge base is offline -----------------------------------------------------------


def test_a_knowledge_base_that_is_offline_fails_at_retrieval_and_never_drafts_without_sources(
    client: TestClient, api_settings: Settings
) -> None:
    inquiry_id = post(client).json()["id"]
    kb = FakeKB([KnowledgeBaseError("unavailable", "could not connect to the knowledge base")])
    llm = FakeLLM([model_reply()])
    assert run(api_settings, inquiry_id, llm, kb) == "failed"
    assert "unavailable" in failed_at(client, inquiry_id, "retrieve")
    assert len(llm.calls) == 1  # the model read the message; nothing was written for the customer
    assert detail(client, inquiry_id)["draft"] is None

    reprocess(client, inquiry_id)
    retry = FakeLLM([GOOD_DRAFT])
    assert run(api_settings, inquiry_id, retry, answering()) == "needs_review"
    assert len(retry.calls) == 1  # only the draft; the message is not read a second time


# --- the database is locked ------------------------------------------------------------------


@contextmanager
def write_lock(path: Path) -> Iterator[None]:
    """Another connection holding the database's write lock, as a second program might."""
    other = sqlite3.connect(str(path), isolation_level=None, timeout=0)
    other.execute("BEGIN IMMEDIATE")
    try:
        yield
    finally:
        other.execute("ROLLBACK")
        other.close()


@pytest.fixture
def short_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """Do not wait the full five seconds for a lock that a test is holding on purpose."""
    monkeypatch.setattr(db, "BUSY_TIMEOUT_SECONDS", 0.05)


@pytest.mark.usefixtures("short_wait")
def test_a_locked_database_refuses_a_new_inquiry_cleanly_and_reading_still_works(
    client: TestClient, api_settings: Settings
) -> None:
    with write_lock(api_settings.db_path):
        response = post(client, body="the kitchen drain gurgles")
        error = assert_error(response, 500, "internal_error")
        assert "gurgles" not in response.text and error["message"]
        assert client.get("/api/status").status_code == 200
        assert client.get("/api/inquiries").status_code == 200  # readers are not blocked
    assert client.get("/api/inquiries").json()["items"] == []  # nothing half stored
    created = post(client)  # and the same request works once the lock is gone
    assert created.status_code == 201 and created.json()["id"] == 1


@pytest.mark.usefixtures("short_wait")
def test_a_locked_database_leaves_a_draft_waiting_and_the_decision_can_be_made_after(
    client: TestClient, api_settings: Settings
) -> None:
    inquiry_id, draft_id = waiting(api_settings)
    with write_lock(api_settings.db_path):
        assert_error(client.post(f"/api/drafts/{draft_id}/approve", json={}), 500, "internal_error")
    assert status_of(client, inquiry_id) == "needs_review"
    assert client.post(f"/api/drafts/{draft_id}/approve", json={}).status_code == 200


def wait_for(condition: Callable[[], bool], timeout: float = 5.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.02)
    return False


@pytest.mark.usefixtures("short_wait")
def test_the_worker_survives_a_locked_database_and_finishes_the_work_after(
    api_settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING)
    with database(api_settings) as conn:
        db.migrate(conn)
        inquiry_id = submit(
            conn,
            NewInquiry.model_validate(
                {"sender_name": "A", "subject": "Drain", "body": "How much for a drain?"}
            ),
            api_settings,
        ).id

    def stored_status() -> str:
        with database(api_settings) as c:
            row = c.execute("SELECT status FROM inquiries WHERE id = ?", (inquiry_id,)).fetchone()
            return str(row["status"])

    worker = pipeline.PipelineWorker(api_settings, poll_seconds=0.05)
    with write_lock(api_settings.db_path):
        worker.start()
        assert wait_for(lambda: any("OperationalError" in r.getMessage() for r in caplog.records))
        assert worker.running  # the thread did not die
        assert stored_status() == "received"  # and the inquiry was not lost or half done
    try:
        assert wait_for(lambda: stored_status() != "received")
    finally:
        worker.stop()
