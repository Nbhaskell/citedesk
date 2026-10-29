"""Phase 8: a size limit and a rate limit on intake, and a request id on every answer."""

import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from citedesk.api import MAX_IMPORT_BYTES, create_app
from citedesk.config import Settings
from citedesk.guards import BodyTooLarge, RateLimiter, max_json_bytes
from tests.golden_data import tuned_golden
from tests.test_api import assert_error, post

# --- how big a request may be ----------------------------------------------------------------


def big_body(settings: Settings) -> bytes:
    return json.dumps({"sender_name": "A", "body": "x" * (max_json_bytes(10_000) + 1)}).encode()


def test_a_request_declared_too_big_is_refused_with_413_and_nothing_is_stored(
    client: TestClient, api_settings: Settings
) -> None:
    response = client.post(
        "/api/inquiries",
        content=big_body(api_settings),
        headers={"content-type": "application/json"},
    )
    assert_error(response, 413, "payload_too_large")
    assert client.get("/api/inquiries").json()["items"] == []


def test_a_request_that_does_not_declare_its_size_is_stopped_as_it_arrives(
    client: TestClient, api_settings: Settings
) -> None:
    body = big_body(api_settings)

    def chunks() -> Iterator[bytes]:
        for start in range(0, len(body), 8192):
            yield body[start : start + 8192]

    response = client.post(
        "/api/inquiries", content=chunks(), headers={"content-type": "application/json"}
    )
    assert_error(response, 413, "payload_too_large")
    assert client.get("/api/inquiries").json()["items"] == []


def test_a_message_at_the_character_limit_is_accepted_even_if_every_character_is_escaped(
    client: TestClient,
) -> None:
    text = "é" * 10_000  # the JSON encoder writes each as a six-byte escape
    payload = json.dumps({"sender_name": "A", "body": text}, ensure_ascii=True).encode()
    assert len(payload) > 60_000
    response = client.post(
        "/api/inquiries", content=payload, headers={"content-type": "application/json"}
    )
    assert response.status_code == 201, response.text


def test_the_ordinary_character_limit_still_answers_with_its_own_error(
    client: TestClient,
) -> None:
    assert_error(post(client, body="x" * 10_001), 422, "invalid_inquiry")


def test_an_upload_over_the_import_limit_is_refused_before_it_is_read(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/inquiries/import",
        content=b"x" * (MAX_IMPORT_BYTES + 1),
        headers={"content-type": "text/csv"},
    )
    assert_error(response, 413, "payload_too_large")


def test_an_import_between_the_two_limits_is_not_refused_for_its_size(client: TestClient) -> None:
    header = "external_id,sender_name,subject,body,channel\n"
    rows = "".join(f"id{n},A,S,{'y' * 300},web_form\n" for n in range(500))  # over 150 KB
    assert len(header + rows) > max_json_bytes(10_000)
    response = client.post(
        "/api/inquiries/import",
        content=(header + rows).encode(),
        headers={"content-type": "text/csv"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["created"] == 500


def test_the_refusal_names_no_text_and_the_limit_is_exported_for_reading() -> None:
    assert BodyTooLarge().status_code == 413
    assert max_json_bytes(10_000) == 10_000 * 6 + 64 * 1024


# --- how fast inquiries may arrive -----------------------------------------------------------


def test_the_window_lets_n_through_then_asks_the_rest_to_wait_and_then_lets_more_through() -> None:
    now = [100.0]
    limiter = RateLimiter(3, clock=lambda: now[0])
    assert [limiter.check() for _ in range(3)] == [None, None, None]
    assert limiter.check() == 60  # the first of the three was just now
    now[0] += 45
    assert limiter.check() == 15
    now[0] += 15  # the three have left the window
    assert limiter.check() is None


def test_zero_turns_the_limit_off() -> None:
    limiter = RateLimiter(0)
    assert all(limiter.check() is None for _ in range(1000))


def test_the_default_limit_lets_the_whole_tuned_set_be_imported_in_a_minute() -> None:
    assert Settings(_env_file=None).intake_rate_limit_per_minute > len(tuned_golden()["items"])


@pytest.fixture
def slow_client(tmp_path: Any) -> Iterator[TestClient]:
    settings = Settings(
        _env_file=None, db_path=tmp_path / "limit.db", intake_rate_limit_per_minute=3
    )
    with TestClient(create_app(settings, start_worker=False), raise_server_exceptions=False) as c:
        yield c


def test_too_many_inquiries_in_a_minute_get_a_429_with_a_wait_and_a_request_id(
    slow_client: TestClient,
) -> None:
    assert [post(slow_client, subject=f"s{n}", body=f"b{n}").status_code for n in range(3)] == [
        201,
        201,
        201,
    ]
    response = post(slow_client, subject="s4", body="b4")
    error = assert_error(response, 429, "rate_limited")
    assert 1 <= int(response.headers["Retry-After"]) <= 60
    assert response.headers["Retry-After"] in error["message"]
    assert len(slow_client.get("/api/inquiries").json()["items"]) == 3  # the fourth was not stored


def test_the_limit_applies_to_imports_too_and_reading_is_never_limited(
    slow_client: TestClient,
) -> None:
    csv = {"content": b"body\nhello\n", "headers": {"content-type": "text/csv"}}
    assert slow_client.post("/api/inquiries/import", **csv).status_code == 200
    for n in range(2):
        assert post(slow_client, subject=f"s{n}", body=f"b{n}").status_code == 201
    assert_error(slow_client.post("/api/inquiries/import", **csv), 429, "rate_limited")
    for _ in range(10):
        assert slow_client.get("/api/inquiries").status_code == 200
        assert slow_client.get("/api/status").status_code == 200


# --- a request id on every answer ------------------------------------------------------------


def test_every_kind_of_answer_carries_a_request_id(
    client: TestClient, api_settings: Settings
) -> None:
    answers = [
        client.get("/api/status"),
        client.get("/api/nope"),
        client.get("/api/inquiries/999"),
        client.get("/api/inquiries?status=bogus"),
        client.post("/api/inquiries", content=b"{", headers={"content-type": "application/json"}),
        client.post(
            "/api/inquiries",
            content=big_body(api_settings),
            headers={"content-type": "application/json"},
        ),
        client.post("/api/inquiries/import", content=b"x", headers={"content-type": "text/plain"}),
        client.delete("/api/status"),
    ]
    for response in answers:
        rid = response.headers.get("X-Request-ID")
        assert rid, f"{response.status_code} {response.request.url} has no request id"
        if response.status_code >= 400:
            assert response.json()["error"]["request_id"] == rid
