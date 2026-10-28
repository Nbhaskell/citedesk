from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi.testclient import TestClient

from citedesk import repo, review
from citedesk.config import Settings
from citedesk.db import connect
from tests.helpers import DRAFT_BODY, in_review
from tests.test_api import assert_error


@contextmanager
def database(settings: Settings) -> Iterator[Any]:
    conn = connect(settings.db_path)
    try:
        yield conn
    finally:
        conn.close()


def waiting(settings: Settings, *, blocked: bool = False) -> tuple[int, int]:
    with database(settings) as conn:
        return in_review(conn, blocked=blocked)


def status_of(client: TestClient, inquiry_id: int) -> str:
    return str(client.get(f"/api/inquiries/{inquiry_id}").json()["inquiry"]["status"])


# --- approve ---------------------------------------------------------------------------------


def test_approve_returns_the_updated_detail(client: TestClient, api_settings: Settings) -> None:
    inquiry_id, draft_id = waiting(api_settings)
    response = client.post(f"/api/drafts/{draft_id}/approve", json={"review_seconds": 30})
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["inquiry"]["status"] == "approved"
    assert detail["draft"]["status"] == "approved"
    assert status_of(client, inquiry_id) == "approved"
    assert [h["event_type"] for h in detail["history"]][-2:] == [
        "status_changed",
        "review_recorded",
    ]


def test_approve_with_an_edit_and_export_return_the_edited_text(
    client: TestClient, api_settings: Settings
) -> None:
    _, draft_id = waiting(api_settings)
    edited = "Hello,\n\nChanged.\n\nKind regards,\nB"
    assert (
        client.post(f"/api/drafts/{draft_id}/approve", json={"edited_body": edited}).status_code
        == 200
    )
    shown = client.get(f"/api/drafts/{draft_id}/export")
    assert shown.json() == {
        "inquiry_id": 1,
        "draft_id": draft_id,
        "subject": "Re: Drain",
        "body": edited,
    }  # noqa: E501


def test_approve_refuses_unknown_fields_and_bad_bodies(
    client: TestClient, api_settings: Settings
) -> None:
    _, draft_id = waiting(api_settings)
    url = f"/api/drafts/{draft_id}/approve"
    assert_error(client.post(url, json={"decision": "approve"}), 422, "validation_error")
    assert_error(client.post(url, json={"edited_body": "  "}), 422, "invalid_review")
    assert_error(client.post(url, json={"review_seconds": -5}), 422, "invalid_review")


def test_approve_errors_do_not_repeat_what_was_sent(
    client: TestClient, api_settings: Settings
) -> None:
    _, draft_id = waiting(api_settings)
    error = assert_error(
        client.post(f"/api/drafts/{draft_id}/approve", json={"edited_body": "x" * 20_000}),
        422,
        "invalid_review",
    )
    assert "xxxx" not in error["message"]


def test_a_blocked_draft_is_refused_with_409(client: TestClient, api_settings: Settings) -> None:
    inquiry_id, draft_id = waiting(api_settings, blocked=True)
    assert_error(client.post(f"/api/drafts/{draft_id}/approve", json={}), 409, "wrong_state")
    assert status_of(client, inquiry_id) == "escalated"


def test_an_unknown_draft_is_404(client: TestClient) -> None:
    assert_error(client.post("/api/drafts/99/approve", json={}), 404, "not_found")
    assert_error(client.get("/api/drafts/99/export"), 404, "not_found")


# --- reject, escalate, resolve ---------------------------------------------------------------


def test_reject_needs_a_reason(client: TestClient, api_settings: Settings) -> None:
    inquiry_id, draft_id = waiting(api_settings)
    url = f"/api/drafts/{draft_id}/reject"
    assert_error(client.post(url, json={}), 422, "validation_error")
    assert_error(client.post(url, json={"reason": " "}), 422, "invalid_review")
    assert status_of(client, inquiry_id) == "needs_review"
    ok = client.post(url, json={"reason": "Wrong price"})
    assert ok.status_code == 200 and ok.json()["inquiry"]["status"] == "rejected"


def test_escalate_then_resolve(client: TestClient, api_settings: Settings) -> None:
    inquiry_id, _ = waiting(api_settings)
    assert_error(
        client.post(f"/api/inquiries/{inquiry_id}/escalate", json={}), 422, "validation_error"
    )
    escalated = client.post(f"/api/inquiries/{inquiry_id}/escalate", json={"note": "Owner please"})
    assert escalated.status_code == 200
    body = escalated.json()
    assert body["inquiry"]["status"] == "escalated"
    assert [e["reason_code"] for e in body["escalations"]] == ["MANUAL"]
    resolved = client.post(f"/api/inquiries/{inquiry_id}/resolve", json={"note": "Phoned them"})
    assert resolved.status_code == 200
    assert resolved.json()["inquiry"]["status"] == "resolved"
    assert all(e["resolved"] for e in resolved.json()["escalations"])


def test_resolve_accepts_an_empty_body(client: TestClient, api_settings: Settings) -> None:
    inquiry_id, _ = waiting(api_settings, blocked=True)
    assert client.post(f"/api/inquiries/{inquiry_id}/resolve", json={}).status_code == 200


def test_wrong_state_is_409_and_unknown_inquiry_is_404(
    client: TestClient, api_settings: Settings
) -> None:
    inquiry_id, _ = waiting(api_settings)
    assert_error(client.post(f"/api/inquiries/{inquiry_id}/resolve", json={}), 409, "wrong_state")
    assert_error(client.post("/api/inquiries/99/escalate", json={"note": "x"}), 404, "not_found")
    assert_error(client.post("/api/inquiries/99/resolve", json={}), 404, "not_found")


# --- export ----------------------------------------------------------------------------------


def test_export_is_refused_until_approval_and_reading_it_changes_nothing(
    client: TestClient, api_settings: Settings
) -> None:
    inquiry_id, draft_id = waiting(api_settings)
    assert_error(client.get(f"/api/drafts/{draft_id}/export"), 409, "wrong_state")
    client.post(f"/api/drafts/{draft_id}/approve", json={})
    assert client.get(f"/api/drafts/{draft_id}/export").json()["body"] == DRAFT_BODY
    assert status_of(client, inquiry_id) == "approved"
    with database(api_settings) as conn:
        assert repo.list_exports(conn, draft_id) == []


def test_posting_the_export_records_the_copy(client: TestClient, api_settings: Settings) -> None:
    inquiry_id, draft_id = waiting(api_settings)
    client.post(f"/api/drafts/{draft_id}/approve", json={})
    response = client.post(f"/api/drafts/{draft_id}/export")
    assert response.status_code == 200 and response.json()["body"] == DRAFT_BODY
    assert status_of(client, inquiry_id) == "exported"
    with database(api_settings) as conn:
        assert len(repo.list_exports(conn, draft_id)) == 1


def test_nothing_in_the_api_sends_anything(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert not [p for p in paths if "send" in p or "mail" in p]


# --- insights --------------------------------------------------------------------------------


def test_insights_on_an_empty_database(client: TestClient) -> None:
    body = client.get("/api/insights").json()
    assert body["total_inquiries"] == 0
    assert body["decisions"] == [{"code": d, "count": 0} for d in (
        "approve", "edit_approve", "reject", "escalate", "resolve")]  # fmt: skip
    assert (body["approved_unchanged_share"], body["edited_share"]) == (None, None)
    assert body["median_review_seconds"] is None
    assert body["synthetic_data"] is True


def test_insights_count_decisions_and_report_shares_and_median(
    client: TestClient, api_settings: Settings
) -> None:
    with database(api_settings) as conn:
        drafts = [in_review(conn)[1] for _ in range(4)]
        review.approve(conn, drafts[0], review_seconds=10)
        review.approve(conn, drafts[1], review_seconds=30)
        review.approve(conn, drafts[2], edited_body="Hello,\n\nEdited.\n\nKind regards,\nB",
                       review_seconds=50)  # fmt: skip
        review.reject(conn, drafts[3], reason="No")
    body = client.get("/api/insights").json()
    counts = {d["code"]: d["count"] for d in body["decisions"]}
    assert counts == {"approve": 2, "edit_approve": 1, "reject": 1, "escalate": 0, "resolve": 0}
    assert body["approved_unchanged_share"] == 2 / 3
    assert body["edited_share"] == 1 / 3
    assert body["median_review_seconds"] == 30
    statuses = {s["code"]: s["count"] for s in body["by_status"]}
    assert (statuses["approved"], statuses["rejected"]) == (3, 1)
    assert body["total_inquiries"] == 4
