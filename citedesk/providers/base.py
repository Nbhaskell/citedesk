"""The model interface (docs/TRD.md section 5).

Everything that talks to a language model goes through `LLMProvider`, so the pipeline never knows
which model it has and tests can run without one.

Errors carry a short reason and never the prompt or the reply, because both hold customer text and
an exception message may be logged.
"""

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


class LLMError(Exception):
    """The model could not give an answer. The message is safe to log."""


class LLMUnavailable(LLMError):
    """Nothing is listening where the model should be."""


class LLMTimeout(LLMError):
    """The model did not answer within the time allowed."""


class LLMBadResponse(LLMError):
    """The server answered, but not with a usable reply."""


@dataclass(frozen=True)
class LLMResult:
    """One model reply. `text` is the raw reply; the caller parses and validates it."""

    text: str
    model: str
    duration_ms: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    truncated: bool = False  # the reply was cut off by the token cap


@runtime_checkable
class LLMProvider(Protocol):
    """Asks a model for a JSON reply that follows `schema`.

    `think` is an addition to the TRD's signature: the understand stage retries once with thinking
    off (TRD 4.2), so the caller has to be able to switch it per call.
    """

    name: str
    model: str

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
    ) -> LLMResult: ...
