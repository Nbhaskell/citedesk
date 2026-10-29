"""What the review screens need beyond the decisions: a summary on each queue row, the counts for
the header, the status checks, the read-only settings, and the figures on Insights."""

import sqlite3
from typing import Any

from fastapi.testclient import TestClient

from citedesk import health, pipeline, repo, review
from citedesk.api import create_app
from citedesk.config import SETTING_ENV_NAMES, Settings
from citedesk.models import InquiryStatus, ReasonCode
from citedesk.providers import FakeLLM
from citedesk.state import transition
from tests.helpers import in_review, model_reply
from tests.test_api_review import database
from tests.test_pipeline_drafting import BUSINESS, store

S = InquiryStatus
HEALTHY: dict[str, dict[str, Any]] = {
    "/api/tags": {"models": [{"name": "qwen3:8b"}]},
    "/api/status": {"chunks": 83},
}


def fake_get(replies: dict[str, dict[str, Any] | str]) -> health.GetFn:
    def get(url: str, timeout_s: float) -> dict[str, Any]:
        for suffix, reply in replies.items():
            if url.endswith(suffix):
                if isinstance(reply, str):
                    raise health.HealthError(reply)
                return reply
        raise health.HealthError("unreachable")

    return get


# --- summary on the queue rows ---------------------------------------------------------------


def test_each_queue_row_carries_the_models_one_line_summary(
    client: TestClient, api_settings: Settings
) -> None:
    with database(api_settings) as conn:
        read = store(conn, api_settings)
        pipeline.process(conn, read, api_settings, llm=FakeLLM([model_reply()]))
        unread = store(conn, api_settings, body="Is anyone there to help with a leak?")
    rows = {r["id"]: r for r in client.get("/api/inquiries").json()["items"]}
    assert rows[read]["summary"] == "Asks how much a kitchen drain costs."
    assert rows[unread]["summary"] is None


def test_a_long_summary_is_cut_for_the_row(client: TestClient, api_settings: Settings) -> None:
    with database(api_settings) as conn:
        inquiry_id = store(conn, api_settings)
        reply = model_reply(summary="Asks about a drain. " * 40)
        pipeline.process(conn, inquiry_id, api_settings, llm=FakeLLM([reply]))
    [row] = client.get("/api/inquiries").json()["items"]
    assert 0 < len(row["summary"]) <= 200


# --- counts for the header -------------------------------------------------------------------


def test_status_counts_what_needs_attention(client: TestClient, api_settings: Settings) -> None:
    empty = client.get("/api/status").json()["attention"]
    assert empty == {"needs_review": 0, "escalated": 0, "failed": 0, "urgent_open": 0}
    with database(api_settings) as conn:
        waiting_a, _ = in_review(conn)
        waiting_b, _ = in_review(conn)
        escalated, _ = in_review(conn, blocked=True)
        repo.update_inquiry(conn, waiting_a, urgency="urgent")
        repo.update_inquiry(conn, escalated, urgency="urgent")
        repo.update_inquiry(conn, waiting_b, urgency="high")
        done, draft = in_review(conn)
        repo.update_inquiry(conn, done, urgency="urgent")
        review.approve(conn, draft)
    counts = client.get("/api/status").json()["attention"]
    assert counts == {"needs_review": 2, "escalated": 1, "failed": 0, "urgent_open": 2}


# --- status checks ---------------------------------------------------------------------------


def test_nothing_is_checked_until_asked_and_the_status_says_so(client: TestClient) -> None:
    body = client.get("/api/status").json()
    assert body["checked_at"] is None
    assert body["components"]["model"] == {"status": "not_checked", "reason": None}


def test_a_check_reports_each_component_and_is_remembered(api_settings: Settings) -> None:
    app = create_app(api_settings, start_worker=False, get_json=fake_get(HEALTHY))
    with TestClient(app) as client:
        checked = client.post("/api/status/check").json()
        assert checked["status"] == "ok"
        assert checked["components"]["model"] == {"status": "ok", "reason": None}
        assert checked["components"]["knowledge_base"] == {"status": "ok", "reason": None}
        assert checked["checked_at"] is not None
        assert client.get("/api/status").json()["checked_at"] == checked["checked_at"]


def test_a_failed_check_degrades_the_status_and_names_the_reason(api_settings: Settings) -> None:
    replies = fake_get({"/api/tags": "unreachable", "/api/status": {"chunks": 0}})
    app = create_app(api_settings, start_worker=False, get_json=replies)
    with TestClient(app) as client:
        body = client.post("/api/status/check").json()
    assert body["status"] == "degraded"
    assert body["components"]["model"] == {"status": "error", "reason": "unreachable"}
    assert body["components"]["knowledge_base"] == {"status": "error", "reason": "not_indexed"}
    assert body["components"]["database"]["status"] == "ok"


def test_a_check_sends_no_inquiry_text_and_leaks_no_address(api_settings: Settings) -> None:
    seen: list[str] = []

    def get(url: str, timeout_s: float) -> dict[str, Any]:
        seen.append(url)
        return HEALTHY["/api/tags"] if url.endswith("/api/tags") else HEALTHY["/api/status"]

    with TestClient(create_app(api_settings, start_worker=False, get_json=get)) as client:
        client.post("/api/inquiries", json={"body": "My secret question about a drain"})
        text = client.post("/api/status/check").text
    assert all("secret" not in url for url in seen)
    assert "http://" not in text and "127.0.0.1" not in text


# --- settings --------------------------------------------------------------------------------


def test_settings_are_read_only_and_describe_what_is_in_force(client: TestClient) -> None:
    response = client.get("/api/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["business"]["name"] == "Kestrel Hollow Plumbing"
    assert body["draft_max_words"] == 200
    assert body["model"] == "qwen3:8b"
    assert body["synthetic_data"] is True
    assert client.post("/api/settings", json={}).status_code == 405
    assert client.put("/api/settings", json={}).status_code == 405


def test_every_escalation_reason_is_listed_with_who_sets_it(client: TestClient) -> None:
    rules = {r["code"]: r for r in client.get("/api/settings").json()["rules"]}
    assert set(rules) == {code.value for code in ReasonCode}
    assert rules["HEALTH_SAFETY"] == {"code": "HEALTH_SAFETY", "enabled": True, "set_by": "code"}
    assert rules["LOW_CONFIDENCE"]["set_by"] == "environment"


def test_the_low_confidence_rule_follows_its_setting(tmp_path: Any) -> None:
    settings = Settings(_env_file=None, db_path=tmp_path / "s.db", escalate_on_low_confidence=False)
    with TestClient(create_app(settings, start_worker=False)) as client:
        rules = {r["code"]: r for r in client.get("/api/settings").json()["rules"]}
    assert rules["LOW_CONFIDENCE"]["enabled"] is False
    assert rules["HEALTH_SAFETY"]["enabled"] is True


def test_settings_show_no_paths_addresses_or_secrets(client: TestClient) -> None:
    text = client.get("/api/settings").text
    for fragment in ("http://", "api.db", "facts.json", "\\\\", ".env"):
        assert fragment not in text
    assert not [name for name in SETTING_ENV_NAMES if name in text]


def test_unreadable_business_facts_are_null_not_an_error(tmp_path: Any) -> None:
    settings = Settings(
        _env_file=None, db_path=tmp_path / "s.db", business_facts_path=tmp_path / "missing.json"
    )
    with TestClient(create_app(settings, start_worker=False)) as client:
        body = client.get("/api/settings").json()
    assert body["business"] is None


def test_business_passed_to_the_app_is_what_settings_show(api_settings: Settings) -> None:
    with TestClient(create_app(api_settings, start_worker=False, business=BUSINESS)) as client:
        business = client.get("/api/settings").json()["business"]
    assert business == {
        "name": BUSINESS.name,
        "phone": BUSINESS.phone,
        "emergency_phone": BUSINESS.emergency_phone,
        "email": BUSINESS.email,
    }


# --- insights: time to draft and the period --------------------------------------------------


def waiting_since(conn: sqlite3.Connection, arrived: str, ready: str) -> int:
    inquiry_id = repo.insert_inquiry(conn, channel="web_form", body="A drain question", now=arrived)
    for step in (S.screened, S.classified, S.routed, S.drafted):
        transition(conn, inquiry_id, step, now=arrived)
    transition(conn, inquiry_id, S.needs_review, now=ready)
    return inquiry_id


def test_insights_report_time_to_draft_with_its_sample_and_period(
    client: TestClient, api_settings: Settings
) -> None:
    empty = client.get("/api/insights").json()
    assert (empty["median_seconds_to_draft"], empty["draft_time_sample"]) == (None, 0)
    assert (empty["period_start"], empty["period_end"]) == (None, None)
    with database(api_settings) as conn:
        waiting_since(conn, "2026-10-28T10:00:00Z", "2026-10-28T10:01:00Z")
        waiting_since(conn, "2026-10-28T11:00:00Z", "2026-10-28T11:02:00Z")
        waiting_since(conn, "2026-10-29T09:00:00Z", "2026-10-29T09:05:00Z")
    body = client.get("/api/insights").json()
    assert (body["median_seconds_to_draft"], body["draft_time_sample"]) == (120, 3)
    assert body["period_start"] == "2026-10-28T10:00:00Z"
    assert body["period_end"] == "2026-10-29T09:00:00Z"


def test_insights_state_how_many_review_times_the_median_rests_on(
    client: TestClient, api_settings: Settings
) -> None:
    with database(api_settings) as conn:
        for seconds in (10, 20, 90):
            _, draft = in_review(conn)
            review.approve(conn, draft, review_seconds=seconds)
        _, rejected = in_review(conn)
        review.reject(conn, rejected, reason="No", review_seconds=500)
    body = client.get("/api/insights").json()
    assert (body["median_review_seconds"], body["review_time_sample"]) == (20, 3)
