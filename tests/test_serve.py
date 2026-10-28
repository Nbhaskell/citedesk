from typing import Any

import pytest

import citedesk.__main__ as entry


def test_server_binds_to_loopback_only(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(entry.uvicorn, "run", lambda app, **kw: calls.append({"app": app, **kw}))
    monkeypatch.setenv("CITEDESK_PORT", "8100")
    entry.main()
    assert len(calls) == 1
    assert calls[0]["host"] == "127.0.0.1"
    assert calls[0]["port"] == 8100


def test_no_setting_can_change_the_bind_host(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(entry.uvicorn, "run", lambda app, **kw: calls.append(kw))
    for name in ("HOST", "CITEDESK_HOST", "UVICORN_HOST"):
        monkeypatch.setenv(name, "0.0.0.0")  # noqa: S104
    entry.main()
    assert calls[0]["host"] == "127.0.0.1"


def test_the_real_server_reads_inquiries_with_the_local_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from citedesk.providers.ollama import OllamaProvider

    seen: dict[str, Any] = {}
    monkeypatch.setattr(entry, "create_app", lambda settings, **kw: seen.update(kw) or "app")
    monkeypatch.setattr(entry.uvicorn, "run", lambda app, **kw: None)
    entry.main()
    assert isinstance(seen["llm"], OllamaProvider)
