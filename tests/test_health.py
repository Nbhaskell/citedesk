"""The model and knowledge-base checks behind Settings and /api/status."""

from typing import Any

import pytest

from citedesk import health
from citedesk.config import Settings
from citedesk.health import HealthError

SETTINGS = Settings(_env_file=None)


def answering(body: dict[str, Any]) -> tuple[list[str], health.GetFn]:
    urls: list[str] = []

    def get(url: str, timeout_s: float) -> dict[str, Any]:
        urls.append(url)
        assert timeout_s <= 5
        return body

    return urls, get


def failing(reason: str) -> health.GetFn:
    def get(url: str, timeout_s: float) -> dict[str, Any]:
        raise HealthError(reason)

    return get


def test_the_model_is_ok_when_the_server_lists_it() -> None:
    urls, get = answering({"models": [{"name": "qwen3:8b", "model": "qwen3:8b"}]})
    assert health.check_model(SETTINGS, get) == health.Check("ok", None)
    assert urls == ["http://127.0.0.1:11434/api/tags"]


def test_an_untagged_model_name_matches_latest() -> None:
    settings = Settings(_env_file=None, llm_model="qwen3")
    _, get = answering({"models": [{"name": "qwen3:latest"}]})
    assert health.check_model(settings, get).status == "ok"


def test_a_model_the_server_does_not_have_is_reported_by_name_of_the_problem() -> None:
    _, get = answering({"models": [{"name": "llama3:8b"}]})
    assert health.check_model(SETTINGS, get) == health.Check("error", "model_missing")


@pytest.mark.parametrize("body", [{}, {"models": "no"}, {"models": [1, 2]}])
def test_an_odd_model_list_is_a_bad_response_not_a_crash(body: dict[str, Any]) -> None:
    _, get = answering(body)
    assert health.check_model(SETTINGS, get).status == "error"


def test_an_unreachable_model_server_is_an_error() -> None:
    assert health.check_model(SETTINGS, failing("unreachable")) == health.Check(
        "error", "unreachable"
    )


def test_the_knowledge_base_is_ok_when_it_has_indexed_passages() -> None:
    urls, get = answering({"files": 8, "chunks": 83})
    assert health.check_knowledge_base(SETTINGS, get) == health.Check("ok", None)
    assert urls == ["http://127.0.0.1:8000/api/status"]


def test_an_empty_index_is_an_error() -> None:
    _, get = answering({"files": 0, "chunks": 0})
    assert health.check_knowledge_base(SETTINGS, get) == health.Check("error", "not_indexed")


@pytest.mark.parametrize("body", [{}, {"chunks": "many"}, {"chunks": True}])
def test_a_knowledge_base_reply_without_a_chunk_count_is_a_bad_response(
    body: dict[str, Any],
) -> None:
    _, get = answering(body)
    assert health.check_knowledge_base(SETTINGS, get) == health.Check("error", "bad_response")


def test_an_unreachable_knowledge_base_is_an_error() -> None:
    assert health.check_knowledge_base(SETTINGS, failing("unreachable")).reason == "unreachable"


@pytest.mark.parametrize("url", ["http://example.com:11434", "http://192.168.1.5:8000", "ftp://x"])
def test_an_address_that_is_not_local_is_never_contacted(url: str) -> None:
    calls: list[str] = []

    def get(u: str, timeout_s: float) -> dict[str, Any]:
        calls.append(u)
        return {}

    model = health.check_model(Settings(_env_file=None, ollama_url=url), get)
    kb = health.check_knowledge_base(Settings(_env_file=None, rag_url=url), get)
    assert (model, kb) == (health.Check("error", "not_local"),) * 2
    assert calls == []


def test_the_real_getter_is_blocked_in_tests() -> None:
    with pytest.raises(AssertionError):
        health.http_get_json("http://127.0.0.1:1/x", 1)
