"""Routing: what a classified inquiry needs next, decided by rules in code (docs/TRD.md 4.3).

Everything here is a pure function of its inputs. The model contributes intents, a confidence and
three flags; this module decides. Nothing the model says can lower the bar for sending a draft.

Order of rules, first match wins, but every matching reason is recorded:

1. Archive: the message screened as spam, the model agrees it is only spam, and nothing else
   applies.
2. Escalate: a safety concern, a complaint, a refund or dispute, a legal threat, a policy
   exception, suspected injection, or low confidence (plus the cases in D-038 and D-039).
3. Request details: a booking-type intent is missing a required field.
4. Draft a reply.
"""

from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from citedesk.models import (
    ClassifiedIntent,
    Confidence,
    EscalationSource,
    Intent,
    ReasonCode,
    Route,
    ScreeningResult,
)

# Required fields per intent (docs/BACKEND_SCHEMA.md section 2). A test compares this table with
# the document. For a booking change or a cancellation the document also allows "sender email
# match"; v1 has no customer or booking table to match against (D-022), so a reference is needed.
REQUIRED_FIELDS: dict[Intent, tuple[str, ...]] = {
    Intent.booking_request: ("service_type", "start_date", "property_type", "address_area"),
    Intent.booking_change: ("start_date", "booking_reference"),
    Intent.availability_question: ("service_type", "start_date"),
    Intent.cancellation: ("booking_reference",),
}

# Reasons the model may flag. The others come from the intent list, the screening result, the
# emergency net or a field, so the model cannot raise or suppress them by name.
MODEL_SIGNALS: frozenset[ReasonCode] = frozenset(
    {ReasonCode.REFUND_OR_DISPUTE, ReasonCode.LEGAL_THREAT, ReasonCode.POLICY_EXCEPTION_REQUEST}
)

_ORDER = {code: position for position, code in enumerate(ReasonCode)}


@dataclass(frozen=True)
class Reason:
    """One reason to escalate. `detail` is fixed wording: it never holds customer text."""

    code: ReasonCode
    source: EscalationSource
    detail: str


@dataclass(frozen=True)
class RouteDecision:
    route: Route
    reasons: tuple[Reason, ...]
    missing_fields: tuple[str, ...]

    @property
    def reason_codes(self) -> list[ReasonCode]:
        return [reason.code for reason in self.reasons]


def is_missing(value: Any) -> bool:
    """A field the customer did not give: absent, blank, or the model's "unknown"."""
    if value is None:
        return True
    return isinstance(value, str) and value.strip().lower() in ("", "unknown")


def _field_values(fields: Mapping[str, Any] | BaseModel) -> Mapping[str, Any]:
    return fields.model_dump() if isinstance(fields, BaseModel) else fields


def missing_fields(
    intents: Iterable[Intent | str], fields: Mapping[str, Any] | BaseModel
) -> list[str]:
    """Required fields still missing for any of the intents, in a stable order."""
    values = _field_values(fields)
    wanted = {Intent(intent) for intent in intents}
    missing: list[str] = []
    for intent in Intent:  # a fixed order, so the answer does not depend on the order asked in
        if intent not in wanted:
            continue
        for name in REQUIRED_FIELDS.get(intent, ()):
            if is_missing(values.get(name)) and name not in missing:
                missing.append(name)
    return missing


def _gather(
    reasons: dict[ReasonCode, list[tuple[EscalationSource, str]]],
    code: ReasonCode,
    source: EscalationSource,
    detail: str,
) -> None:
    reasons.setdefault(code, []).append((source, detail))


def decide_route(
    *,
    intents: Sequence[ClassifiedIntent],
    primary_confidence: Confidence,
    fields: Mapping[str, Any] | BaseModel,
    signals: Collection[ReasonCode] = (),
    screening_result: ScreeningResult = ScreeningResult.clean,
    safety_net_hit: bool = False,
    escalate_on_low_confidence: bool = True,
) -> RouteDecision:
    """Choose the route and list every reason behind an escalation.

    `signals` are the codes the model flagged beyond its intents. Urgency is not an input: it
    orders the queue and does not route.
    """
    if not intents:
        raise ValueError("at least one intent is needed to route an inquiry")
    bad = set(signals) - MODEL_SIGNALS
    if bad:
        raise ValueError(f"the model may not flag these as a signal: {sorted(bad)}")

    kinds = {item.intent for item in intents}
    values = _field_values(fields)
    only_spam = kinds == {Intent.spam}
    gathered: dict[ReasonCode, list[tuple[EscalationSource, str]]] = {}
    rule = EscalationSource.rule

    if Intent.health_or_safety in kinds:
        _gather(gathered, ReasonCode.HEALTH_SAFETY, rule, "classified as health or safety")
    if safety_net_hit:
        _gather(
            gathered,
            ReasonCode.HEALTH_SAFETY,
            EscalationSource.safety_net,
            "emergency terms found in the message",
        )
    if Intent.complaint in kinds:
        _gather(gathered, ReasonCode.COMPLAINT, rule, "classified as a complaint")
    for code in signals:
        _gather(gathered, code, rule, "flagged by the model")
    if values.get("property_type") == "commercial":
        _gather(
            gathered,
            ReasonCode.POLICY_EXCEPTION_REQUEST,
            rule,
            "commercial property; the business serves homes only",
        )
    if screening_result is ScreeningResult.injection_suspected:
        _gather(gathered, ReasonCode.INJECTION_SUSPECTED, rule, "injection patterns at screening")
    if escalate_on_low_confidence and primary_confidence is Confidence.low:
        _gather(gathered, ReasonCode.LOW_CONFIDENCE, rule, "primary intent confidence is low")
    if only_spam and screening_result is ScreeningResult.clean:
        _gather(
            gathered,
            ReasonCode.LOW_CONFIDENCE,
            rule,
            "the model says spam but screening does not",
        )

    reasons = tuple(
        Reason(
            code=code,
            # The net is credited only when it alone raised the reason (TRD 4.2).
            source=(
                EscalationSource.safety_net
                if all(origin is EscalationSource.safety_net for origin, _ in found)
                else rule
            ),
            detail="; ".join(dict.fromkeys(detail for _, detail in found)),
        )
        for code, found in sorted(gathered.items(), key=lambda item: _ORDER[item[0]])
    )
    missing = tuple(missing_fields(kinds, values))

    if reasons:
        route = Route.escalate
    elif only_spam and screening_result is ScreeningResult.spam:
        route = Route.archive
    elif missing:
        route = Route.request_details
    else:
        route = Route.draft_reply
    return RouteDecision(route=route, reasons=reasons, missing_fields=missing)
