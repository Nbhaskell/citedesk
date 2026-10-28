"""Language-model providers: the interface, a scripted fake for tests, and Ollama."""

from citedesk.providers.base import (
    LLMBadResponse,
    LLMError,
    LLMProvider,
    LLMResult,
    LLMStepFailed,
    LLMTimeout,
    LLMUnavailable,
)
from citedesk.providers.fake import FakeLLM, LLMCall

__all__ = [
    "FakeLLM",
    "LLMBadResponse",
    "LLMCall",
    "LLMError",
    "LLMProvider",
    "LLMResult",
    "LLMStepFailed",
    "LLMTimeout",
    "LLMUnavailable",
]
