"""The API answers only its own machine's names, and only pages from them may change things (D-092).

A page on another site could otherwise read the queue through DNS rebinding (its own name made to
point at 127.0.0.1, so the browser treats the API as same-origin), or post a form to an endpoint
that takes no body, such as reprocess. Tools that are not browsers send no Origin and still work.
"""

import pytest
from fastapi.testclient import TestClient

from citedesk.api import create_app
from citedesk.config import Settings
from citedesk.guards import host_allowed, origin_allowed

LOCAL = frozenset({"127.0.0.1", "localhost", "::1"})


@pytest.mark.parametrize(
    "host",
    ["127.0.0.1", "127.0.0.1:8100", "localhost", "localhost:5174", "[::1]:8100", "LOCALHOST"],
)
def test_the_machines_own_names_are_allowed(host: str) -> None:
    assert host_allowed(host, LOCAL)


@pytest.mark.parametrize(
    "host",
    ["", "evil.example.com", "evil.example.com:8100", "127.0.0.1.evil.example", "localhost.evil"],
)
def test_other_names_are_refused(host: str) -> None:
    assert not host_allowed(host, LOCAL)


@pytest.mark.parametrize(
    "origin",
    [
        None,
        "http://127.0.0.1:5174",
        "http://localhost:5174",
        "http://[::1]:5174",
        "http://127.0.0.1",
    ],
)
def test_no_origin_or_a_local_page_may_change_things(origin: str | None) -> None:
    assert origin_allowed(origin, LOCAL)


@pytest.mark.parametrize(
    "origin",
    ["null", "https://evil.example.com", "http://127.0.0.1.evil.example", "file://", "garbage"],
)
def test_a_page_from_elsewhere_may_not(origin: str) -> None:
    assert not origin_allowed(origin, LOCAL)


@pytest.fixture
def local_client(api_settings: Settings) -> TestClient:
    return TestClient(
        create_app(api_settings, start_worker=False), base_url="http://127.0.0.1:8100"
    )


def test_a_request_with_a_foreign_host_is_refused(local_client: TestClient) -> None:
    with local_client as client:
        response = client.get("/api/inquiries", headers={"Host": "evil.example.com"})
    assert response.status_code == 400
    body = response.json()["error"]
    assert body["code"] == "host_not_allowed"
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_a_local_host_is_served(local_client: TestClient) -> None:
    with local_client as client:
        assert client.get("/api/inquiries").status_code == 200
        assert client.get("/api/inquiries", headers={"Host": "localhost:5174"}).status_code == 200


def test_a_post_from_a_foreign_page_is_refused_and_changes_nothing(
    local_client: TestClient,
) -> None:
    with local_client as client:
        response = client.post(
            "/api/inquiries/1/reprocess", headers={"Origin": "https://evil.example.com"}
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "origin_not_allowed"
        new = {"channel": "web_form", "body": "Is the shop open on Saturday?"}
        refused = client.post("/api/inquiries", json=new, headers={"Origin": "null"})
        assert refused.status_code == 403
        assert client.get("/api/inquiries").json()["items"] == []


def test_a_post_from_the_web_app_or_a_tool_goes_ahead(local_client: TestClient) -> None:
    new = {"channel": "web_form", "body": "Is the shop open on Saturday?"}
    with local_client as client:
        page = client.post("/api/inquiries", json=new, headers={"Origin": "http://127.0.0.1:5174"})
        tool = client.post("/api/inquiries", json={**new, "body": "And on Sunday?"})
    assert page.status_code == 201
    assert tool.status_code == 201


def test_reads_from_a_foreign_page_are_left_to_the_browser(local_client: TestClient) -> None:
    # With a local Host, a read from another origin is not refused here: the browser does not let
    # that page see the answer, because the API sends no CORS headers.
    with local_client as client:
        response = client.get("/api/inquiries", headers={"Origin": "https://evil.example.com"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
