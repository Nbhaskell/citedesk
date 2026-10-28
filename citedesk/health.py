"""Is the model server reachable and does it have the model; does the knowledge base have passages.

Run only when someone asks (Settings, or `POST /api/status/check`), never on each status poll.
Both checks are plain GET requests with a short limit to a loopback address; no inquiry text is
sent. A result is a status and a short reason code, never the address or the server's reply.
"""

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlparse

from citedesk.config import Settings
from citedesk.providers.ollama import LOOPBACK_HOSTS

GetFn = Callable[[str, float], dict[str, Any]]
TIMEOUT_S = 2.0


class HealthError(Exception):
    """A check could not get an answer. `reason` is a short code."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Check:
    status: Literal["ok", "error"]
    reason: str | None


def http_get_json(url: str, timeout_s: float) -> dict[str, Any]:
    request = urllib.request.Request(url, method="GET")  # noqa: S310 (loopback only, see _is_local)
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
            raw = response.read()
    except (urllib.error.URLError, OSError):  # includes HTTP errors and timeouts
        raise HealthError("unreachable") from None
    try:
        body = json.loads(raw)
    except ValueError:
        raise HealthError("bad_response") from None
    if not isinstance(body, dict):
        raise HealthError("bad_response")
    return body


def _is_local(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and parsed.hostname in LOOPBACK_HOSTS


def _fetch(url: str, path: str, get: GetFn | None) -> dict[str, Any]:
    if not _is_local(url):
        raise HealthError("not_local")
    return (get or http_get_json)(url.rstrip("/") + path, TIMEOUT_S)


def check_model(settings: Settings, get: GetFn | None = None) -> Check:
    try:
        body = _fetch(settings.ollama_url, "/api/tags", get)
    except HealthError as error:
        return Check("error", error.reason)
    models = body.get("models")
    if not isinstance(models, list) or not all(isinstance(m, dict) for m in models):
        return Check("error", "bad_response")
    names = {str(m.get("name")) for m in models} | {str(m.get("model")) for m in models}
    wanted = settings.llm_model
    if wanted in names or f"{wanted}:latest" in names:
        return Check("ok", None)
    return Check("error", "model_missing")


def check_knowledge_base(settings: Settings, get: GetFn | None = None) -> Check:
    try:
        body = _fetch(settings.rag_url, "/api/status", get)
    except HealthError as error:
        return Check("error", error.reason)
    chunks = body.get("chunks")
    if not isinstance(chunks, int) or isinstance(chunks, bool):
        return Check("error", "bad_response")
    return Check("ok", None) if chunks > 0 else Check("error", "not_indexed")
