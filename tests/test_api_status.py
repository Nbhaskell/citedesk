import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import citedesk
from citedesk import api
from citedesk.api import create_app
from citedesk.config import Settings


def test_status_returns_json_200(client: TestClient) -> None:
    response = client.get("/api/status")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")


def test_status_body_shape(client: TestClient) -> None:
    body = client.get("/api/status").json()
    assert body["status"] == "ok"
    assert body["app"] == "citedesk"
    assert body["version"] == citedesk.__version__
    assert body["synthetic_data"] is True
    assert body["model"] == "qwen3:8b"
    assert set(body) == {
        "status",
        "app",
        "version",
        "synthetic_data",
        "model",
        "components",
        "queue_depth",
        "worker_running",
        "attention",
        "checked_at",
    }


def test_the_database_is_really_checked_and_the_rest_honestly_are_not(client: TestClient) -> None:
    components = client.get("/api/status").json()["components"]
    assert set(components) == {"database", "model", "knowledge_base"}
    assert components["database"]["status"] == "ok"
    assert components["model"]["status"] == "not_checked"  # until POST /api/status/check
    assert components["knowledge_base"]["status"] == "not_checked"


def test_queue_depth_counts_inquiries_waiting_for_the_pipeline(client: TestClient) -> None:
    assert client.get("/api/status").json()["queue_depth"] == 0
    for n in range(3):
        assert (
            client.post("/api/inquiries", json={"body": f"question {n} about a drain"}).status_code
            == 201
        )
    assert client.get("/api/status").json()["queue_depth"] == 3


def test_the_worker_flag_reflects_whether_it_runs(api_settings: Settings) -> None:
    with TestClient(create_app(api_settings, start_worker=False)) as off:
        assert off.get("/api/status").json()["worker_running"] is False
    with TestClient(create_app(api_settings, start_worker=True, worker_poll_seconds=0.05)) as on:
        assert on.get("/api/status").json()["worker_running"] is True
    with TestClient(create_app(api_settings, start_worker=False)) as after:
        assert after.get("/api/status").json()["worker_running"] is False


def test_a_broken_database_is_reported_not_hidden(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: object, **kwargs: object) -> sqlite3.Connection:
        raise sqlite3.OperationalError("unable to open database file")

    monkeypatch.setattr(api, "connect", boom)
    response = client.get("/api/status")
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "degraded"
    assert body["components"]["database"]["status"] == "error"
    assert "unable to open" not in response.text


def test_status_reports_synthetic_flag_from_settings(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, db_path=tmp_path / "s.db", synthetic_data=False)
    with TestClient(create_app(settings, start_worker=False)) as client:
        assert client.get("/api/status").json()["synthetic_data"] is False


def test_status_does_not_leak_paths_or_urls(client: TestClient) -> None:
    text = client.get("/api/status").text
    assert "api.db" not in text
    assert "http://" not in text


def test_unknown_route_is_404_with_the_error_shape(client: TestClient) -> None:
    response = client.get("/api/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_status_is_read_only(client: TestClient) -> None:
    response = client.post("/api/status")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"
