"""A scripted model for tests: no network, no GPU, no randomness."""

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from citedesk.providers.base import LLMResult

Reply = str | dict[str, Any] | list[Any] | Exception | LLMResult


@dataclass(frozen=True)
class LLMCall:
    """What the pipeline asked the model, kept so a test can look at it."""

    system: str
    user: str
    schema: dict[str, Any]
    temperature: float
    max_tokens: int
    timeout_s: int
    seed: int | None
    think: bool


class FakeLLM:
    """Replies from a script: a list used in order, or a function of the call.

    A reply that is an exception is raised instead of returned. A dict or list is sent as JSON
    text; a string is sent as it is, so a test can send invalid JSON; an `LLMResult` is returned
    untouched, for a test that needs a truncated reply or token counts. Running out of scripted
    replies is a test bug, so it raises AssertionError.
    """

    name = "fake"

    def __init__(
        self,
        replies: Iterable[Reply] | Callable[[LLMCall], Reply] = (),
        *,
        model: str = "fake-model",
        asks_exception: bool | Callable[[LLMCall], Reply] = False,
    ) -> None:
        """`asks_exception` answers the single-purpose exception question (a call whose schema has
        an `asks_for_exception` field): a bool, or a function of the call. Those calls are kept in
        `exception_calls` and never use the scripted replies, so a test that scripts the main
        reading is not disturbed by the extra question."""
        self.model = model
        self._asks_exception = asks_exception
        self.exception_calls: list[LLMCall] = []
        self.calls: list[LLMCall] = []
        self._function = replies if callable(replies) else None
        self._queue: list[Reply] = [] if callable(replies) else list(replies)

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
        call = LLMCall(system, user, schema, temperature, max_tokens, timeout_s, seed, think)
        if "asks_for_exception" in schema.get("properties", {}):
            self.exception_calls.append(call)
            reply = (
                self._asks_exception(call)
                if callable(self._asks_exception)
                else {"asks_for_exception": self._asks_exception}
            )
            if isinstance(reply, Exception):
                raise reply
            if isinstance(reply, LLMResult):
                return reply
            text = reply if isinstance(reply, str) else json.dumps(reply)
            return LLMResult(text=text, model=self.model, duration_ms=1)
        self.calls.append(call)
        if self._function is not None:
            reply = self._function(call)
        elif self._queue:
            reply = self._queue.pop(0)
        else:
            raise AssertionError("FakeLLM was called more times than it has replies")
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, LLMResult):
            return reply
        text = reply if isinstance(reply, str) else json.dumps(reply)
        return LLMResult(text=text, model=self.model, duration_ms=1)
