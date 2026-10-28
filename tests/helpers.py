"""Shared builders for tests that need a scripted model reply."""

from typing import Any

from citedesk.models import ReasonCode
from citedesk.routing import MODEL_SIGNALS

FIELD_KEYS = (
    "service_type",
    "start_date",
    "property_type",
    "address_area",
    "preferred_contact",
    "booking_reference",
    "dates_as_written",
)


def model_reply(**over: Any) -> dict[str, Any]:
    """A valid reply from the understand prompt: a plain drain-price question."""
    base: dict[str, Any] = {
        "summary": "Asks how much a kitchen drain costs.",
        "intents": [{"intent": "pricing_question", "confidence": "high"}],
        "primary_intent": "pricing_question",
        "urgency": "normal",
        "sentiment": "neutral",
        "escalation_signals": [],
        "fields": dict.fromkeys(FIELD_KEYS) | {"service_type": "drain_cleaning"},
    }
    base.update(over)
    return base


def perfect_reply(item: dict[str, Any]) -> dict[str, Any]:
    """What a model that read the golden labels would say, for an end-to-end test."""
    labels = item["labels"]
    reasons = {ReasonCode(code) for code in labels["expected_reason_codes"]}
    confidence = "low" if ReasonCode.LOW_CONFIDENCE in reasons else "high"
    return {
        "summary": "A customer message.",
        "intents": [{"intent": name, "confidence": confidence} for name in labels["intents"]],
        "primary_intent": labels["primary_intent"],
        "urgency": labels["urgency"],
        "sentiment": "neutral",
        "escalation_signals": sorted(code.value for code in reasons & MODEL_SIGNALS),
        "fields": dict.fromkeys(FIELD_KEYS) | labels["fields"],
    }
