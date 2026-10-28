"""The knowledge base behind `KnowledgeBase`: rag-project over HTTP, and a scripted fake.

Customer questions go to the knowledge base, so its address must be this machine (the same rule as
the model's). Errors say what went wrong and never repeat the question.

rag-project has no "declined" flag, so the adapter decides (docs/knowledge-base-contract.md, D-045):
a reply is a decline when it lists no sources, or when its first sentence is a refusal.
"""

import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, ValidationError

from citedesk.models import Source
from citedesk.providers.ollama import LOOPBACK_HOSTS

MAX_QUESTION_CHARS = 2000  # rag-project's own limit
TIMEOUT_S = 120

# What a refusal sounds like when rag-project's model declines in words (contract: the same
# question can be a refusal with sources listed one run and with none the next).
REFUSAL = re.compile(
    r"^(?:i\s+(?:do\s*n[o']t|don’t|do\s+not)\s+know"
    r"|i(?:'m|’m|\s+am)\s+not\s+sure"
    r"|i\s+(?:cannot|can(?:'t|’t|not))\s+(?:find|answer)"
    r"|there\s+is\s+no\s+information"
    r"|(?:the\s+)?(?:documents?|context|provided\s+context|sources?)\s+"
    r"(?:do(?:es)?\s+not|don't|doesn't)\s+(?:say|mention|contain|cover|provide|include|specify))",
    re.IGNORECASE,
)
SENTENCE_END = re.compile(r"(?<=[.!?])\s")


class KnowledgeBaseError(Exception):
    """The knowledge base could not answer. `reason` is a short code; the message is safe to log."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class KBResult:
    answer: str
    declined: bool
    sources: list[Source]
    raw: dict[str, Any] = field(default_factory=dict)
    decline_reason: str | None = None  # "no_sources" or "refusal" when declined


@runtime_checkable
class KnowledgeBase(Protocol):
    def ask(self, question: str, *, history: list[str] | None = None) -> KBResult: ...


def is_refusal(answer: str) -> bool:
    """True if the answer's first sentence declines to answer (or the answer is empty)."""
    text = answer.strip()
    if not text:
        return True
    first = SENTENCE_END.split(text, maxsplit=1)[0]
    return bool(REFUSAL.match(first.strip()))


PostFn = Callable[[str, dict[str, Any], float], dict[str, Any]]


def http_post_json(url: str, payload: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    request = urllib.request.Request(  # noqa: S310 (the host is checked in RagProjectKB)
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
            raw = response.read()
    except urllib.error.HTTPError as error:
        raise KnowledgeBaseError(
            "bad_response", f"the knowledge base answered HTTP {error.code}"
        ) from None
    except TimeoutError:
        raise KnowledgeBaseError("timeout", f"no answer within {timeout_s:g} seconds") from None
    except (urllib.error.URLError, OSError):
        raise KnowledgeBaseError("unavailable", "could not connect to the knowledge base") from None
    try:
        body = json.loads(raw)
    except ValueError:
        raise KnowledgeBaseError(
            "bad_response", "the knowledge base's reply was not JSON"
        ) from None
    if not isinstance(body, dict):
        raise KnowledgeBaseError("bad_response", "the knowledge base's reply was not an object")
    return body


class _Passage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source: str
    section: str | None = None
    page: int | None = None
    text: str
    listed: bool = False


class _Reply(BaseModel):
    model_config = ConfigDict(extra="ignore")

    answer: str
    passages: list[_Passage] = []


class RagProjectKB:
    """`POST /api/ask` on rag-project (default http://127.0.0.1:8000)."""

    def __init__(self, base_url: str, *, post: PostFn | None = None) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("the knowledge base address must start with http:// or https://")
        if parsed.hostname not in LOOPBACK_HOSTS:
            raise ValueError(
                "the knowledge base address must be a loopback address (127.0.0.1, localhost or "
                "::1): questions come from customer messages and stay on this machine"
            )
        self._base_url = base_url.rstrip("/")
        self._post = post

    def ask(self, question: str, *, history: list[str] | None = None) -> KBResult:
        payload: dict[str, Any] = {"question": question.strip()[:MAX_QUESTION_CHARS]}
        if history:
            payload["history"] = [{"role": "user", "content": line} for line in history]
        post = self._post or http_post_json  # looked up per call so tests can replace it
        body = post(f"{self._base_url}/api/ask", payload, TIMEOUT_S)
        try:
            reply = _Reply.model_validate(body)
        except ValidationError:
            raise KnowledgeBaseError(
                "bad_response", "the knowledge base's reply was not in the expected shape"
            ) from None
        sources = [
            Source(file=p.source, section=p.section or "", page=p.page, text=p.text)
            for p in reply.passages
            if p.listed
        ]
        reason = "no_sources" if not sources else "refusal" if is_refusal(reply.answer) else None
        return KBResult(
            answer=reply.answer,
            declined=reason is not None,
            sources=sources,
            raw=body,
            decline_reason=reason,
        )


class FakeKB:
    """A scripted knowledge base for tests: replies in order, or a function of the question."""

    def __init__(
        self, replies: Iterable[KBResult | Exception] | Callable[[str], KBResult | Exception] = ()
    ) -> None:
        self.questions: list[str] = []
        self._function = replies if callable(replies) else None
        self._queue: list[KBResult | Exception] = [] if callable(replies) else list(replies)

    def ask(self, question: str, *, history: list[str] | None = None) -> KBResult:
        self.questions.append(question)
        if self._function is not None:
            reply = self._function(question)
        elif self._queue:
            reply = self._queue.pop(0)
        else:
            raise AssertionError("FakeKB was asked more times than it has replies")
        if isinstance(reply, Exception):
            raise reply
        return reply

    @staticmethod
    def answered(
        answer: str, files: list[str], *, text: str = "A passage from the documents."
    ) -> KBResult:
        sources = [Source(file=f, section=f"{f} section", page=None, text=text) for f in files]
        return KBResult(answer=answer, declined=False, sources=sources, raw={})

    @staticmethod
    def declined() -> KBResult:
        return KBResult(
            answer="I don't know.", declined=True, sources=[], raw={}, decline_reason="no_sources"
        )


def timed(kb: KnowledgeBase, question: str) -> tuple[KBResult, int]:
    """Ask and measure the time on this side, which includes the network and any queueing."""
    started = time.monotonic()
    result = kb.ask(question)
    return result, int((time.monotonic() - started) * 1000)
