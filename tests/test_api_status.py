from fastapi.testclient import TestClient

import citedesk
from citedesk.api import create_app
from citedesk.config import Settings


def make_client(**overrides: object) -> TestClient:
    return TestClient(create_app(Settings(_env_file=None, **overrides)))  # type: ignore[arg-type]


def test_status_returns_json_200() -> None:
    response = make_client().get("/api/status")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")


def test_status_body_shape() -> None:
    body = make_client().get("/api/status").json()
    assert body["status"] == "ok"
    assert body["app"] == "citedesk"
    assert body["version"] == citedesk.__version__
    assert body["synthetic_data"] is True
    assert body["model"] == "qwen3:8b"


def test_status_does_not_claim_health_it_has_not_checked() -> None:
    components = make_client().get("/api/status").json()["components"]
    assert set(components) == {"database", "model", "knowledge_base"}
    assert all(c["status"] == "not_checked" for c in components.values())


def test_status_reports_synthetic_flag_from_settings() -> None:
    body = make_client(synthetic_data=False).get("/api/status").json()
    assert body["synthetic_data"] is False


def test_status_does_not_leak_paths_or_urls() -> None:
    text = make_client().get("/api/status").text
    assert "citedesk.db" not in text
    assert "http://" not in text


def test_unknown_route_is_404() -> None:
    assert make_client().get("/api/nope").status_code == 404


def test_status_is_read_only() -> None:
    assert make_client().post("/api/status").status_code == 405
