import contextlib
import json
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from citedesk.config import Settings
from citedesk.providers import (
    LLMBadResponse,
    LLMProvider,
    LLMTimeout,
    LLMUnavailable,
)
from citedesk.providers.ollama import OllamaProvider, http_post_json

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
CUSTOMER_TEXT = "my kitchen sink smells of gas and my name is Alex"


def envelope(content: str = '{"ok": true}', **over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": "qwen3:8b",
        "created_at": "2026-10-28T12:00:00Z",
        "message": {"role": "assistant", "content": content},
        "done": True,
        "done_reason": "stop",
        "total_duration": 2_000_000_000,
        "prompt_eval_count": 120,
        "eval_count": 30,
    }
    body.update(over)
    return body


class Recorder:
    """A stand-in for the HTTP call that remembers what it was given."""

    def __init__(self, reply: dict[str, Any] | Exception) -> None:
        self.reply = reply
        self.calls: list[tuple[str, dict[str, Any], float]] = []

    def __call__(self, url: str, payload: dict[str, Any], timeout_s: float) -> dict[str, Any]:
        self.calls.append((url, payload, timeout_s))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def provider(reply: dict[str, Any] | Exception | None = None, **over: Any) -> tuple[Any, Recorder]:
    recorder = Recorder(envelope() if reply is None else reply)
    return OllamaProvider("http://127.0.0.1:11434", "qwen3:8b", post=recorder, **over), recorder


def ask(llm: OllamaProvider, **over: Any) -> Any:
    return llm.generate_json(system="be brief", user=CUSTOMER_TEXT, schema=SCHEMA, **over)


# --- the request ------------------------------------------------------------------------------


def test_the_request_follows_the_chat_api_with_the_trd_settings() -> None:
    llm, recorder = provider()
    ask(llm)
    [(url, payload, timeout_s)] = recorder.calls
    assert url == "http://127.0.0.1:11434/api/chat"
    assert payload["model"] == "qwen3:8b"
    assert payload["stream"] is False
    assert payload["format"] == SCHEMA
    assert payload["think"] is False
    assert payload["messages"] == [
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": CUSTOMER_TEXT},
    ]
    assert payload["options"] == {
        "temperature": 0.0,
        "seed": 0,
        "num_predict": 1500,
        "num_ctx": 8192,
    }
    assert timeout_s == 120


def test_settings_for_one_call_are_passed_through() -> None:
    llm, recorder = provider(num_ctx=4096)
    ask(llm, temperature=0.2, max_tokens=800, timeout_s=30, seed=None, think=True)
    [(_, payload, timeout_s)] = recorder.calls
    assert payload["think"] is True
    assert payload["options"] == {
        "temperature": 0.2,
        "num_predict": 800,
        "num_ctx": 4096,
    }
    assert timeout_s == 30


def test_a_trailing_slash_on_the_address_is_harmless() -> None:
    recorder = Recorder(envelope())
    OllamaProvider("http://localhost:11434/", "m", post=recorder).generate_json(
        system="s", user="u", schema=SCHEMA
    )
    assert recorder.calls[0][0] == "http://localhost:11434/api/chat"


# --- the reply --------------------------------------------------------------------------------


def test_the_reply_text_and_counts_are_returned() -> None:
    llm, _ = provider(envelope('{"ok": false}'))
    result = ask(llm)
    assert result.text == '{"ok": false}'
    assert result.model == "qwen3:8b"
    assert (result.prompt_tokens, result.completion_tokens) == (120, 30)
    assert result.truncated is False
    assert result.duration_ms >= 0


def test_a_reply_cut_off_by_the_token_cap_is_marked_truncated() -> None:
    llm, _ = provider(envelope('{"ok": tr', done_reason="length"))
    assert ask(llm).truncated is True


def test_thinking_text_is_not_part_of_the_reply() -> None:
    reply = envelope()
    reply["message"]["thinking"] = "Let me think about the customer..."
    result = ask(provider(reply)[0])
    assert result.text == '{"ok": true}'


@pytest.mark.parametrize(
    "reply",
    [
        {},
        {"message": None},
        {"message": {"role": "assistant"}},
        {"message": {"role": "assistant", "content": ""}},
        {"message": {"role": "assistant", "content": "   "}},
        {"message": {"role": "assistant", "content": 7}},
        {"error": "model not found"},
    ],
    ids=["empty", "no-message", "no-content", "blank", "spaces", "not-text", "error-body"],
)
def test_an_unusable_envelope_is_a_bad_response(reply: dict[str, Any]) -> None:
    llm, _ = provider(reply)
    with pytest.raises(LLMBadResponse) as caught:
        ask(llm)
    assert CUSTOMER_TEXT not in str(caught.value)


def test_a_prompt_that_fills_the_context_window_is_refused() -> None:
    llm, _ = provider(envelope(prompt_eval_count=8192 - 10), num_ctx=8192)
    with pytest.raises(LLMBadResponse, match="context window"):
        ask(llm)


def test_errors_from_the_http_call_pass_through_untouched() -> None:
    for error in (LLMTimeout("slow"), LLMUnavailable("down"), LLMBadResponse("bad")):
        llm, _ = provider(error)
        with pytest.raises(type(error)):
            ask(llm)


# --- where it may send customer text ----------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:11434",
        "http://localhost:11434",
        "http://[::1]:11434",
        "https://127.0.0.1:11434",
    ],
)
def test_loopback_addresses_are_accepted(url: str) -> None:
    OllamaProvider(url, "m", post=Recorder(envelope()))


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com:11434",
        "http://192.168.1.20:11434",
        "http://0.0.0.0:11434",
        "http://127.0.0.1.example.com:11434",
        "ftp://127.0.0.1:11434",
        "127.0.0.1:11434",
        "",
    ],
)
def test_any_other_address_is_refused_because_it_would_send_messages_off_the_machine(
    url: str,
) -> None:
    with pytest.raises(ValueError, match="loopback|http"):
        OllamaProvider(url, "m", post=Recorder(envelope()))


def test_it_is_built_from_settings() -> None:
    settings = Settings(_env_file=None, ollama_url="http://127.0.0.1:9999", llm_model="tiny")
    llm = OllamaProvider.from_settings(settings, post=Recorder(envelope()))
    assert (llm.name, llm.model) == ("ollama", "tiny")
    assert isinstance(llm, LLMProvider)


# --- the real HTTP call, against a stand-in server on loopback --------------------------------


@contextmanager
def stand_in_server(
    respond: Callable[[BaseHTTPRequestHandler, dict[str, Any]], None],
) -> Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 (name set by the base class)
            length = int(self.headers.get("Content-Length", "0"))
            respond(self, json.loads(self.rfile.read(length)))

        def log_message(self, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()


def send(handler: BaseHTTPRequestHandler, status: int, body: bytes) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def test_a_json_reply_is_parsed() -> None:
    seen: list[dict[str, Any]] = []

    def respond(handler: BaseHTTPRequestHandler, payload: dict[str, Any]) -> None:
        seen.append(payload)
        send(handler, 200, json.dumps(envelope()).encode())

    with stand_in_server(respond) as base:
        reply = http_post_json(f"{base}/api/chat", {"model": "m"}, 5)
    assert reply["message"]["content"] == '{"ok": true}'
    assert seen == [{"model": "m"}]


def test_a_server_error_is_a_bad_response_that_does_not_repeat_the_body() -> None:
    def respond(handler: BaseHTTPRequestHandler, payload: dict[str, Any]) -> None:
        send(handler, 500, json.dumps({"error": f"failed on: {CUSTOMER_TEXT}"}).encode())

    with stand_in_server(respond) as base, pytest.raises(LLMBadResponse) as caught:
        http_post_json(f"{base}/api/chat", {"model": "m"}, 5)
    assert "500" in str(caught.value)
    assert CUSTOMER_TEXT not in str(caught.value)


def test_a_reply_that_is_not_json_is_a_bad_response() -> None:
    def respond(handler: BaseHTTPRequestHandler, payload: dict[str, Any]) -> None:
        send(handler, 200, b"<html>proxy error</html>")

    with stand_in_server(respond) as base, pytest.raises(LLMBadResponse):
        http_post_json(f"{base}/api/chat", {"model": "m"}, 5)


def test_a_reply_that_is_json_but_not_an_object_is_a_bad_response() -> None:
    def respond(handler: BaseHTTPRequestHandler, payload: dict[str, Any]) -> None:
        send(handler, 200, b"[1, 2]")

    with stand_in_server(respond) as base, pytest.raises(LLMBadResponse):
        http_post_json(f"{base}/api/chat", {"model": "m"}, 5)


def test_a_server_that_takes_too_long_is_a_timeout() -> None:
    def respond(handler: BaseHTTPRequestHandler, payload: dict[str, Any]) -> None:
        time.sleep(1.0)
        with contextlib.suppress(OSError):  # the client has already given up
            send(handler, 200, json.dumps(envelope()).encode())

    with stand_in_server(respond) as base, pytest.raises(LLMTimeout):
        http_post_json(f"{base}/api/chat", {"model": "m"}, 0.2)


def test_nothing_listening_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    # A refused connection can take seconds to report on Windows, so the refusal is simulated.
    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise urllib.error.URLError(ConnectionRefusedError(f"refused: {CUSTOMER_TEXT}"))

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    with pytest.raises(LLMUnavailable) as caught:
        http_post_json("http://127.0.0.1:1/api/chat", {"model": CUSTOMER_TEXT}, 5)
    assert CUSTOMER_TEXT not in str(caught.value)
    assert caught.value.__cause__ is None


def test_a_connection_that_times_out_while_connecting_is_unavailable_not_slow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def hang(*args: Any, **kwargs: Any) -> Any:
        raise urllib.error.URLError(TimeoutError("timed out"))

    monkeypatch.setattr(urllib.request, "urlopen", hang)
    with pytest.raises(LLMUnavailable):
        http_post_json("http://127.0.0.1:1/api/chat", {"model": "m"}, 5)
