"""Routing is plain code, so it gets exhaustive tests (docs/TRD.md section 4.3).

Three layers: the required-fields table against the schema document, every rule on its own and in
the order TRD 4.3 gives, and invariants checked over the whole cross product of the inputs.
"""

import itertools
import random
import re
from pathlib import Path
from typing import Any

import pytest

from citedesk import routing
from citedesk.models import (
    ClassifiedIntent,
    Confidence,
    EscalationSource,
    ExtractedFields,
    Intent,
    ReasonCode,
    Route,
    ScreeningResult,
)
from citedesk.routing import REQUIRED_FIELDS, decide_route, is_missing, missing_fields

REPO_ROOT = Path(__file__).resolve().parent.parent
R = ReasonCode
I = Intent  # noqa: E741 (reads better in the tables below)

COMPLETE_BOOKING: dict[str, Any] = {
    "service_type": "drain_cleaning",
    "start_date": "2026-11-06",
    "property_type": "house",
    "address_area": "Millrace",
    "booking_reference": "KH-1042",
}


def intents(*names: Intent, confidence: Confidence = Confidence.high) -> list[ClassifiedIntent]:
    return [ClassifiedIntent(intent=name, confidence=confidence) for name in names]


def decide(*names: Intent, **over: Any) -> routing.RouteDecision:
    args: dict[str, Any] = {
        "intents": intents(*names),
        "primary_confidence": Confidence.high,
        "fields": COMPLETE_BOOKING,
    }
    args.update(over)
    return decide_route(**args)


def codes(decision: routing.RouteDecision) -> list[ReasonCode]:
    return [reason.code for reason in decision.reasons]


# --- the required-fields table ---------------------------------------------------------------


def test_the_table_matches_the_schema_document() -> None:
    text = (REPO_ROOT / "docs/BACKEND_SCHEMA.md").read_text("utf-8")
    section = text.split("## 2. Required fields per intent", 1)[1].split("## 3.", 1)[0]
    documented: dict[Intent, tuple[str, ...]] = {}
    for line in section.splitlines():
        match = re.match(r"^\| `(\w+)` \| (.+) \|$", line)
        if match:
            documented[Intent(match.group(1))] = tuple(re.findall(r"`(\w+)`", match.group(2)))
    assert documented, "no rows found in the schema document"
    # "or sender email match" cannot be satisfied in v1 (there is no customer table; D-022), so
    # the booking reference is the only way to find a booking.
    assert documented == REQUIRED_FIELDS


def test_every_required_field_is_a_field_the_model_extracts() -> None:
    known = set(ExtractedFields.model_fields)
    for intent, names in REQUIRED_FIELDS.items():
        assert set(names) <= known, intent


def test_only_intents_with_requirements_are_listed() -> None:
    assert set(REQUIRED_FIELDS) == {
        I.booking_request,
        I.booking_change,
        I.availability_question,
        I.cancellation,
    }


@pytest.mark.parametrize("value", [None, "", "   ", "unknown", "UNKNOWN", " Unknown "])
def test_these_values_count_as_missing(value: Any) -> None:
    assert is_missing(value)


@pytest.mark.parametrize("value", ["house", "2026-11-06", "other", "0", 0, False])
def test_these_values_count_as_present(value: Any) -> None:
    assert not is_missing(value)


@pytest.mark.parametrize(
    ("names", "fields", "expected"),
    [
        ((I.pricing_question,), {}, []),
        ((I.booking_request,), {}, ["service_type", "start_date", "property_type", "address_area"]),
        ((I.booking_request,), COMPLETE_BOOKING, []),
        ((I.booking_request,), {**COMPLETE_BOOKING, "start_date": None}, ["start_date"]),
        ((I.booking_request,), {**COMPLETE_BOOKING, "service_type": "unknown"}, ["service_type"]),
        ((I.booking_request,), {**COMPLETE_BOOKING, "property_type": "unknown"}, ["property_type"]),
        ((I.booking_request,), {**COMPLETE_BOOKING, "address_area": "  "}, ["address_area"]),
        (
            (I.booking_change,),
            {**COMPLETE_BOOKING, "booking_reference": None},
            ["booking_reference"],
        ),
        ((I.booking_change,), {"booking_reference": "KH-1"}, ["start_date"]),
        ((I.cancellation,), {"booking_reference": None}, ["booking_reference"]),
        ((I.cancellation,), {"booking_reference": "KH-1"}, []),
        ((I.availability_question,), {"service_type": "drain_cleaning"}, ["start_date"]),
        ((I.availability_question,), {"start_date": "2026-11-06"}, ["service_type"]),
        ((I.complaint, I.health_or_safety, I.spam, I.other), {}, []),
    ],
)
def test_missing_fields(
    names: tuple[Intent, ...], fields: dict[str, Any], expected: list[str]
) -> None:
    assert missing_fields(names, fields) == expected


def test_a_field_missing_for_two_intents_is_listed_once_in_a_stable_order() -> None:
    names = (I.availability_question, I.booking_request)
    assert missing_fields(names, {}) == [
        "service_type",
        "start_date",
        "property_type",
        "address_area",
    ]
    assert missing_fields(tuple(reversed(names)), {}) == [
        "service_type",
        "start_date",
        "property_type",
        "address_area",
    ]


def test_missing_fields_takes_the_model_too() -> None:
    fields = ExtractedFields.model_validate(
        {
            "service_type": "drain_cleaning",
            "start_date": None,
            "property_type": "unknown",
            "address_area": None,
            "preferred_contact": None,
            "booking_reference": None,
            "dates_as_written": "next Tuesday",
        }
    )
    assert missing_fields([I.booking_request], fields) == [
        "start_date",
        "property_type",
        "address_area",
    ]


# --- each rule on its own --------------------------------------------------------------------


def test_a_complete_ordinary_question_gets_a_draft() -> None:
    decision = decide(I.pricing_question)
    assert decision.route is Route.draft_reply
    assert decision.reasons == () and decision.missing_fields == ()


def test_a_complete_booking_gets_a_draft() -> None:
    assert decide(I.booking_request).route is Route.draft_reply


def test_an_incomplete_booking_asks_for_details() -> None:
    decision = decide(I.booking_request, fields={**COMPLETE_BOOKING, "start_date": None})
    assert decision.route is Route.request_details
    assert decision.missing_fields == ("start_date",)
    assert decision.reasons == ()


def test_a_missing_field_for_an_intent_the_customer_did_not_ask_is_ignored() -> None:
    assert decide(I.pricing_question, fields={}).route is Route.draft_reply


@pytest.mark.parametrize(
    ("kwargs", "code", "source"),
    [
        ({"names": (I.health_or_safety,)}, R.HEALTH_SAFETY, EscalationSource.rule),
        (
            {"names": (I.pricing_question,), "safety_net_hit": True},
            R.HEALTH_SAFETY,
            EscalationSource.safety_net,
        ),
        ({"names": (I.complaint,)}, R.COMPLAINT, EscalationSource.rule),
        (
            {"names": (I.billing_question,), "signals": [R.REFUND_OR_DISPUTE]},
            R.REFUND_OR_DISPUTE,
            EscalationSource.rule,
        ),
        (
            {"names": (I.service_question,), "signals": [R.LEGAL_THREAT]},
            R.LEGAL_THREAT,
            EscalationSource.rule,
        ),
        (
            {"names": (I.policy_question,), "signals": [R.POLICY_EXCEPTION_REQUEST]},
            R.POLICY_EXCEPTION_REQUEST,
            EscalationSource.rule,
        ),
        (
            {"names": (I.pricing_question,), "signals": [R.INJECTION_SUSPECTED]},
            R.INJECTION_SUSPECTED,
            EscalationSource.rule,
        ),
        (
            {
                "names": (I.pricing_question,),
                "screening_result": ScreeningResult.injection_suspected,
            },
            R.INJECTION_SUSPECTED,
            EscalationSource.rule,
        ),
        (
            {"names": (I.pricing_question,), "primary_confidence": Confidence.low},
            R.LOW_CONFIDENCE,
            EscalationSource.rule,
        ),
        (
            {
                "names": (I.pricing_question,),
                "fields": {**COMPLETE_BOOKING, "property_type": "commercial"},
            },
            R.POLICY_EXCEPTION_REQUEST,
            EscalationSource.rule,
        ),
    ],
    ids=[
        "health-intent",
        "safety-net",
        "complaint",
        "refund",
        "legal",
        "policy-exception",
        "injection-signal",
        "injection",
        "low-confidence",
        "commercial-property",
    ],
)
def test_each_escalation_trigger_escalates_with_its_own_code(
    kwargs: dict[str, Any], code: ReasonCode, source: EscalationSource
) -> None:
    names = kwargs["names"]
    decision = decide(*names, **{k: v for k, v in kwargs.items() if k != "names"})
    assert decision.route is Route.escalate
    assert codes(decision) == [code]
    assert decision.reasons[0].source is source


def test_reasons_carry_a_short_fixed_detail_with_no_customer_text() -> None:
    decision = decide(
        I.health_or_safety,
        I.complaint,
        signals=[R.REFUND_OR_DISPUTE, R.LEGAL_THREAT, R.POLICY_EXCEPTION_REQUEST],
        safety_net_hit=True,
        primary_confidence=Confidence.low,
        screening_result=ScreeningResult.injection_suspected,
    )
    for reason in decision.reasons:
        assert 0 < len(reason.detail) <= 120
        assert reason.detail.isascii()


def test_low_confidence_is_ignored_when_the_switch_is_off() -> None:
    decision = decide(
        I.pricing_question, primary_confidence=Confidence.low, escalate_on_low_confidence=False
    )
    assert decision.route is Route.draft_reply


def test_medium_confidence_is_enough() -> None:
    assert (
        decide(I.pricing_question, primary_confidence=Confidence.medium).route is Route.draft_reply
    )


def test_a_low_confidence_guess_at_a_secondary_intent_does_not_escalate() -> None:
    # Only the primary intent's confidence matters (TRD 4.3).
    mixed = [
        ClassifiedIntent(intent=I.pricing_question, confidence=Confidence.high),
        ClassifiedIntent(intent=I.other, confidence=Confidence.low),
    ]
    assert (
        decide_route(intents=mixed, primary_confidence=Confidence.high, fields={}).route
        is Route.draft_reply
    )


def test_urgent_by_itself_does_not_escalate() -> None:
    # Urgency is not an input at all: it orders the queue, it does not route.
    assert "urgency" not in routing.decide_route.__annotations__


# --- spam and the archive rule ---------------------------------------------------------------


def test_spam_only_with_a_spam_screening_is_archived() -> None:
    decision = decide(I.spam, screening_result=ScreeningResult.spam)
    assert decision.route is Route.archive and decision.reasons == ()


def test_spam_with_a_real_intent_is_not_archived() -> None:
    decision = decide(I.spam, I.pricing_question, screening_result=ScreeningResult.spam)
    assert decision.route is Route.draft_reply


def test_an_emergency_term_beats_the_archive_rule() -> None:
    decision = decide(I.spam, screening_result=ScreeningResult.spam, safety_net_hit=True)
    assert decision.route is Route.escalate and codes(decision) == [R.HEALTH_SAFETY]


def test_a_model_that_says_spam_when_screening_does_not_is_sent_to_a_person() -> None:
    # TRD 4.3 archives only on a high spam score. The model alone cannot archive (D-038).
    decision = decide(I.spam, screening_result=ScreeningResult.clean)
    assert decision.route is Route.escalate
    assert codes(decision) == [R.LOW_CONFIDENCE]
    assert decision.reasons[0].source is EscalationSource.rule


def test_that_rule_does_not_depend_on_the_low_confidence_switch() -> None:
    decision = decide(I.spam, escalate_on_low_confidence=False)
    assert decision.route is Route.escalate


def test_injection_beats_spam() -> None:
    decision = decide(I.spam, screening_result=ScreeningResult.injection_suspected)
    assert decision.route is Route.escalate and codes(decision) == [R.INJECTION_SUSPECTED]


# --- order: archive, then escalate, then request details, then draft --------------------------


def test_escalation_beats_request_details() -> None:
    decision = decide(I.booking_request, I.complaint, fields={})
    assert decision.route is Route.escalate
    # The gaps are still recorded, so the reviewer sees what was missing.
    assert decision.missing_fields == (
        "service_type",
        "start_date",
        "property_type",
        "address_area",
    )


def test_a_commercial_booking_is_escalated_not_asked_for_details() -> None:
    decision = decide(I.booking_request, fields={"property_type": "commercial"})
    assert decision.route is Route.escalate and codes(decision) == [R.POLICY_EXCEPTION_REQUEST]


def test_a_commercial_cafe_question_is_escalated_too() -> None:
    decision = decide(I.service_question, fields={"property_type": "commercial"})
    assert decision.route is Route.escalate


def test_other_property_types_do_not_escalate() -> None:
    for kind in ("house", "apartment", "other"):
        fields = {**COMPLETE_BOOKING, "property_type": kind}
        assert decide(I.booking_request, fields=fields).route is Route.draft_reply
    for kind in ("unknown", None):  # not known is not commercial: ask
        fields = {**COMPLETE_BOOKING, "property_type": kind}
        decision = decide(I.booking_request, fields=fields)
        assert decision.route is Route.request_details
        assert decision.missing_fields == ("property_type",)


def test_all_matching_reasons_are_recorded_in_schema_order() -> None:
    decision = decide(
        I.complaint,
        I.health_or_safety,
        signals=[R.LEGAL_THREAT, R.REFUND_OR_DISPUTE],
        screening_result=ScreeningResult.injection_suspected,
        primary_confidence=Confidence.low,
    )
    assert codes(decision) == [
        R.HEALTH_SAFETY,
        R.COMPLAINT,
        R.REFUND_OR_DISPUTE,
        R.LEGAL_THREAT,
        R.INJECTION_SUSPECTED,
        R.LOW_CONFIDENCE,
    ]


def test_the_model_flagging_safety_wins_the_source_over_the_net() -> None:
    decision = decide(I.health_or_safety, safety_net_hit=True)
    assert [r.source for r in decision.reasons] == [EscalationSource.rule]


def test_two_triggers_for_one_code_make_one_reason() -> None:
    decision = decide(
        I.policy_question,
        signals=[R.POLICY_EXCEPTION_REQUEST],
        fields={"property_type": "commercial"},
    )
    assert codes(decision) == [R.POLICY_EXCEPTION_REQUEST]
    assert "commercial" in decision.reasons[0].detail


def test_signals_can_only_be_the_four_codes_the_model_may_flag() -> None:
    for bad in (R.HEALTH_SAFETY, R.COMPLAINT, R.LOW_CONFIDENCE, R.MANUAL):
        with pytest.raises(ValueError, match="signal"):
            decide(I.pricing_question, signals=[bad])


def test_at_least_one_intent_is_required() -> None:
    with pytest.raises(ValueError, match="intent"):
        decide_route(intents=[], primary_confidence=Confidence.high, fields={})


# --- invariants over the whole cross product of inputs ---------------------------------------

INTENT_POOL = (
    I.spam,
    I.health_or_safety,
    I.complaint,
    I.booking_request,
    I.cancellation,
    I.pricing_question,
)
SUBSETS = [
    combo
    for size in range(1, len(INTENT_POOL) + 1)
    for combo in itertools.combinations(INTENT_POOL, size)
]
SIGNAL_SETS = [
    combo
    for size in range(4)
    for combo in itertools.combinations(
        (R.REFUND_OR_DISPUTE, R.LEGAL_THREAT, R.POLICY_EXCEPTION_REQUEST), size
    )
]
FIELD_SETS = [
    {},
    COMPLETE_BOOKING,
    {**COMPLETE_BOOKING, "property_type": "commercial"},
]


INTENT_LISTS = {names: intents(*names) for names in SUBSETS}


def every_input() -> Any:
    return itertools.product(
        SUBSETS,
        list(Confidence),
        list(ScreeningResult),
        (False, True),
        SIGNAL_SETS,
        FIELD_SETS,
        (False, True),
    )


def test_the_invariants_hold_for_every_combination_of_inputs() -> None:
    count = 0
    for names, confidence, screening, net, signals, fields, switch in every_input():
        decision = decide_route(
            intents=INTENT_LISTS[names],
            primary_confidence=confidence,
            fields=fields,
            signals=signals,
            screening_result=screening,
            safety_net_hit=net,
            escalate_on_low_confidence=switch,
        )
        count += 1
        where = (names, confidence, screening, net, signals, fields, switch)
        found = codes(decision)
        only_spam = set(names) == {I.spam}

        assert len(found) == len(set(found)), where
        assert found == sorted(found, key=list(ReasonCode).index), where

        # The route follows from the reasons and the gaps, in TRD order.
        if decision.route is Route.archive:
            assert found == [] and only_spam and screening is ScreeningResult.spam and not net, (
                where
            )
        elif decision.route is Route.escalate:
            assert found, where
        elif decision.route is Route.request_details:
            assert found == [] and decision.missing_fields, where
        else:
            assert decision.route is Route.draft_reply
            assert found == [] and not decision.missing_fields, where

        # Things that must always escalate, whatever else is true.
        must = (
            I.health_or_safety in names
            or net
            or I.complaint in names
            or bool(signals)
            or screening is ScreeningResult.injection_suspected
            or fields.get("property_type") == "commercial"
            or (confidence is Confidence.low and switch)
            or (only_spam and screening is ScreeningResult.clean)
        )
        assert (decision.route is Route.escalate) == bool(must), where
        if I.health_or_safety in names or net:
            assert R.HEALTH_SAFETY in found, where
        if I.complaint in names:
            assert R.COMPLAINT in found, where
        for signal in signals:
            assert signal in found, where
    assert count == len(SUBSETS) * 3 * 3 * 2 * len(SIGNAL_SETS) * len(FIELD_SETS) * 2


def test_the_order_of_the_intents_never_matters() -> None:
    generator = random.Random(0)  # noqa: S311 (a fixed seed for a test, not security)
    for names, confidence, screening, net, signals, fields, switch in itertools.islice(
        every_input(), 0, None, 97
    ):
        shuffled = list(names)
        generator.shuffle(shuffled)
        results = [
            decide_route(
                intents=intents(*order),
                primary_confidence=confidence,
                fields=fields,
                signals=signals,
                screening_result=screening,
                safety_net_hit=net,
                escalate_on_low_confidence=switch,
            )
            for order in (names, tuple(shuffled))
        ]
        assert results[0] == results[1]


def test_the_order_of_the_signals_never_matters() -> None:
    forward = decide(I.pricing_question, signals=[R.LEGAL_THREAT, R.REFUND_OR_DISPUTE])
    backward = decide(I.pricing_question, signals=[R.REFUND_OR_DISPUTE, R.LEGAL_THREAT])
    assert forward == backward


def test_deciding_twice_gives_the_same_answer_and_changes_nothing() -> None:
    given = {**COMPLETE_BOOKING, "start_date": None}
    snapshot = dict(given)
    first = decide(I.booking_request, fields=given)
    second = decide(I.booking_request, fields=given)
    assert first == second and given == snapshot


def test_the_model_can_only_add_an_injection_reason_never_remove_one() -> None:
    by_screening = decide(I.pricing_question, screening_result=ScreeningResult.injection_suspected)
    assert codes(by_screening) == [R.INJECTION_SUSPECTED]
    both = decide(
        I.pricing_question,
        screening_result=ScreeningResult.injection_suspected,
        signals=[R.INJECTION_SUSPECTED],
    )
    assert codes(both) == [R.INJECTION_SUSPECTED]  # one reason, not two
    only_model = decide(I.pricing_question, signals=[R.INJECTION_SUSPECTED])
    assert only_model.route is Route.escalate
    assert decide(I.pricing_question).route is Route.draft_reply  # no signal, no change
