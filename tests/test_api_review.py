from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi.testclient import TestClient

from citedesk import pipeline, repo, review
from citedesk.api import create_app
from citedesk.config import Settings
from citedesk.db import connect
from citedesk.providers import FakeLLM
from citedesk.state import transition
from tests.helpers import DRAFT_BODY, in_review
from tests.test_api import assert_error
from tests.test_pipeline_drafting import BUSINESS, GOOD_DRAFT, NOW, drafted


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


# --- redraft and reprocess -------------------------------------------------------------------

REDRAFT: dict[str, Any] = {
    "subject": "Re: Drain price",
    "body": "Hi Alex,\n\nDrain cleaning starts at $149.\n\nKind regards,\nKestrel Hollow Plumbing",
    "claims": [{"text": "starts at $149", "source_index": 0}],
}


@contextmanager
def drafting_client(settings: Settings, replies: list[Any]) -> Iterator[TestClient]:
    app = create_app(settings, start_worker=False, llm=FakeLLM(replies), business=BUSINESS)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def reject_a_draft(settings: Settings) -> tuple[int, int]:
    with database(settings) as conn:
        inquiry_id = drafted(conn, settings, GOOD_DRAFT)
        pipeline.check_stage(conn, inquiry_id, settings, BUSINESS, now=NOW)
        draft = repo.latest_draft(conn, inquiry_id)
        assert draft is not None
        review.reject(conn, draft.id, reason="Too long")
        return inquiry_id, draft.id


def test_redraft_returns_the_detail_with_a_new_version(api_settings: Settings) -> None:
    with drafting_client(api_settings, [REDRAFT]) as client:
        inquiry_id, draft_id = reject_a_draft(api_settings)
        response = client.post(f"/api/drafts/{draft_id}/redraft", json={"guidance": "Shorter"})
        assert response.status_code == 200, response.text
        detail = response.json()
        assert detail["inquiry"]["status"] == "needs_review"
        assert (detail["draft"]["version"], detail["draft"]["guidance"]) == (2, "Shorter")
        assert detail["draft"]["status"] == "ready"
        assert status_of(client, inquiry_id) == "needs_review"


def test_redraft_needs_the_model_to_be_connected(
    client: TestClient, api_settings: Settings
) -> None:
    _, draft_id = reject_a_draft(api_settings)
    assert_error(
        client.post(f"/api/drafts/{draft_id}/redraft", json={"guidance": "Shorter"}),
        503,
        "model_unavailable",
    )


def test_redraft_refusals(api_settings: Settings) -> None:
    with drafting_client(api_settings, []) as client:
        _, draft_id = reject_a_draft(api_settings)
        url = f"/api/drafts/{draft_id}/redraft"
        assert_error(client.post(url, json={}), 422, "validation_error")
        assert_error(client.post(url, json={"guidance": " "}), 422, "invalid_review")
        missing = client.post("/api/drafts/99/redraft", json={"guidance": "x"})
        assert_error(missing, 404, "not_found")
        waiting_id, waiting_draft = waiting(api_settings)
        not_rejected = client.post(f"/api/drafts/{waiting_draft}/redraft", json={"guidance": "x"})
        assert_error(not_rejected, 409, "wrong_state")
        assert status_of(client, waiting_id) == "needs_review"


def test_a_model_that_fails_is_a_502_and_the_item_stays_rejected(api_settings: Settings) -> None:
    with drafting_client(api_settings, ["not json", "not json"]) as client:
        inquiry_id, draft_id = reject_a_draft(api_settings)
        error = assert_error(
            client.post(f"/api/drafts/{draft_id}/redraft", json={"guidance": "Shorter"}),
            502,
            "model_failed",
        )
        assert "not json" not in error["message"]
        assert status_of(client, inquiry_id) == "rejected"


def test_reprocess_puts_a_failed_inquiry_back(client: TestClient, api_settings: Settings) -> None:
    with database(api_settings) as conn:
        inquiry_id = drafted(conn, api_settings, GOOD_DRAFT)
        transition(
            conn,
            inquiry_id,
            "failed",
            failure_stage="check",
            failure_message="The check stage crashed twice",
        )
    response = client.post(f"/api/inquiries/{inquiry_id}/reprocess")
    assert response.status_code == 200, response.text
    assert response.json()["inquiry"]["status"] == "drafted"
    assert response.json()["inquiry"]["failure_stage"] is None
    assert_error(client.post(f"/api/inquiries/{inquiry_id}/reprocess"), 409, "wrong_state")
    assert_error(client.post("/api/inquiries/99/reprocess"), 404, "not_found")


# --- the aids beside a draft (D-077) -------------------------------------------------------


def test_a_model_written_reply_comes_with_its_support(
    client: TestClient, api_settings: Settings
) -> None:
    inquiry_id, _ = waiting(api_settings)
    support = client.get(f"/api/inquiries/{inquiry_id}").json()["support"]
    assert support is not None
    assert {"greeting_name", "figures", "sentences"} <= set(support)
    assert all(
        s["status"] in {"supported", "routine", "from_message", "unsupported"}
        for s in support["sentences"]
    )
    assert any(f["figure"] == "$175" for f in support["figures"])


def test_support_is_computed_from_the_draft_and_changes_nothing_stored(
    client: TestClient, api_settings: Settings
) -> None:
    inquiry_id, draft_id = waiting(api_settings)
    first = client.get(f"/api/inquiries/{inquiry_id}").json()
    second = client.get(f"/api/inquiries/{inquiry_id}").json()
    assert first["support"] == second["support"]
    assert first["draft"] == second["draft"] and first["draft"]["id"] == draft_id


def test_an_inquiry_without_a_draft_has_no_support(
    client: TestClient, api_settings: Settings
) -> None:
    created = client.post(
        "/api/inquiries",
        json={"channel": "web_form", "body": "How much is a drain?", "sender_name": "A"},
    )
    assert created.status_code in (200, 201), created.text
    inquiry_id = created.json()["id"] if "id" in created.json() else created.json()["inquiry"]["id"]
    assert client.get(f"/api/inquiries/{inquiry_id}").json()["support"] is None
