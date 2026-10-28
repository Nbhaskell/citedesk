"""The Ollama provider: a local model behind `LLMProvider`.

It posts to Ollama's `/api/chat` with a JSON schema in `format`, thinking switched per call, and
the token cap, seed and context size in `options`. Customer text goes in the prompt, so the address
must be this machine: a mistyped `OLLAMA_URL` must not send messages to a hosted service.
"""

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from citedesk.config import Settings
from citedesk.providers.base import LLMBadResponse, LLMResult, LLMTimeout, LLMUnavailable

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
# Ollama's own default is smaller and silently drops the start of a long prompt.
DEFAULT_NUM_CTX = 8192
CONTEXT_MARGIN = 64  # tokens; a prompt this close to the window is probably truncated

PostFn = Callable[[str, dict[str, Any], float], dict[str, Any]]


def http_post_json(url: str, payload: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    """POST a JSON body and return the JSON object that comes back.

    Errors say what went wrong and never repeat the request or the reply, which hold customer text.
    """
    request = urllib.request.Request(  # noqa: S310 (the scheme and host are checked in OllamaProvider)
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
            raw = response.read()
    except urllib.error.HTTPError as error:
        raise LLMBadResponse(f"the model server answered HTTP {error.code}") from None
    except TimeoutError:  # raised while waiting for the reply, once the connection was made
        raise LLMTimeout(f"no answer within {timeout_s:g} seconds") from None
    except (urllib.error.URLError, OSError):  # includes a timeout while connecting
        raise LLMUnavailable("could not connect to the model server") from None
    try:
        body = json.loads(raw)
    except ValueError:
        raise LLMBadResponse("the model server's reply was not JSON") from None
    if not isinstance(body, dict):
        raise LLMBadResponse("the model server's reply was not a JSON object")
    return body


def _check_address(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("the model address must start with http:// or https://")
    if parsed.hostname not in LOOPBACK_HOSTS:
        raise ValueError(
            "the model address must be a loopback address (127.0.0.1, localhost or ::1): "
            "messages are sent to it, and v1 keeps them on this machine"
        )
    return base_url.rstrip("/")


class OllamaProvider:
    name = "ollama"

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        num_ctx: int = DEFAULT_NUM_CTX,
        post: PostFn | None = None,
    ) -> None:
        self._base_url = _check_address(base_url)
        self.model = model
        self._num_ctx = num_ctx
        self._post = post

    @classmethod
    def from_settings(cls, settings: Settings, *, post: PostFn | None = None) -> "OllamaProvider":
        return cls(settings.ollama_url, settings.llm_model, post=post)

    def generate_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        temperature: float = 0.0,
        max_tokens: int = 1500,
        timeout_s: int = 120,
        seed: int | None = 0,
        think: bool = False,
    ) -> LLMResult:
        options: dict[str, Any] = {
            "temperature": temperature,
            "num_predict": max_tokens,
            "num_ctx": self._num_ctx,
        }
        if seed is not None:
            options["seed"] = seed
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "format": schema,
            "think": think,
            "options": options,
        }
        post = self._post or http_post_json  # looked up per call so tests can replace it
        started = time.monotonic()
        body = post(f"{self._base_url}/api/chat", payload, timeout_s)
        elapsed_ms = int((time.monotonic() - started) * 1000)

        message = body.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise LLMBadResponse("the model's reply had no text")
        prompt_tokens = _count(body.get("prompt_eval_count"))
        if prompt_tokens is not None and prompt_tokens >= self._num_ctx - CONTEXT_MARGIN:
            raise LLMBadResponse("the prompt filled the context window, so part of it was lost")
        return LLMResult(
            text=content,
            model=self.model,
            duration_ms=elapsed_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=_count(body.get("eval_count")),
            truncated=body.get("done_reason") == "length",
        )


def _count(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
