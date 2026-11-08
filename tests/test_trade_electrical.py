"""The electrical trade (D-098): its emergency terms, its customer vocabulary and its prompts.

Every sentence here is invented. The emergency terms err towards firing, as the plumbing ones do: a
missed emergency costs far more than an extra look from a person.
"""

import pytest

from citedesk import screening, understand
from citedesk.models import ServiceType
from citedesk.safety import emergency_hits
from citedesk.trade import ELECTRICAL, PLUMBING


def hits(text: str) -> list[str]:
    return emergency_hits(text, ELECTRICAL.emergency_patterns, ELECTRICAL.imaginable)


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("There is a burning smell coming from the outlet in the bedroom.", "burning_smell"),
        ("It smells like melting plastic near the panel.", "burning_smell"),
        ("The switch sparked when I flipped it.", "sparks_or_smoke"),
        ("Sparks came out of the socket.", "sparks_or_smoke"),
        ("There is smoke coming out of the light fixture.", "sparks_or_smoke"),
        ("The ceiling fan caught fire.", "sparks_or_smoke"),
        ("I got a shock from the kitchen tap light switch.", "shock"),
        ("My son got a small shock when he touched the dryer.", "shock"),
        ("Electric shock from the outlet near the sink.", "shock"),
        ("There are exposed wires hanging from the ceiling.", "exposed_wires"),
        ("The outlet is hot to the touch.", "hot_fitting"),
        ("The breaker is buzzing and blackened.", "hot_fitting"),
        ("A power line is down across our driveway.", "downed_line"),
        ("Water is dripping into the light fixture from upstairs.", "water_and_electrics"),
        ("The basement flooded and the panel is wet.", "water_and_electrics"),
        ("I smell gas near the stove.", "gas_smell"),
        ("Our carbon monoxide alarm is going off.", "carbon_monoxide"),
    ],
)
def test_an_electrical_emergency_fires(text: str, name: str) -> None:
    assert name in hits(text), (text, hits(text))


@pytest.mark.parametrize(
    "text",
    [
        "How much is a panel upgrade to 200 amps?",
        "I would like a quote for a new breaker panel.",
        "Can you add a breaker for the hot tub?",
        "I was shocked at the price of the last electrician.",
        "Please install three recessed lights in the kitchen.",
        "Do you install EV chargers in a detached garage?",
        "Can you replace a light switch with a dimmer?",
        "We are selling the house and need an electrical inspection.",
        "Our fuse box is old; do you replace them?",
    ],
)
def test_an_ordinary_electrical_question_does_not_fire(text: str) -> None:
    assert hits(text) == [], (text, hits(text))


def test_a_spark_in_the_past_does_not_fire_but_one_today_does() -> None:
    assert hits("An outlet sparked last year and was replaced.") == []
    assert hits("An outlet sparked last year and it sparked again today.") != []


def test_an_imagined_electrical_emergency_still_fires() -> None:
    assert hits("What should I do if an outlet sparks?") != []


def test_the_plumbing_panel_rule_does_not_apply_to_the_electrical_trade() -> None:
    # For a plumber, an electrical panel is out of scope and worth a look; for an electrician, it
    # is everyday work.
    assert "electrical" in emergency_hits("Water is near the electrical panel.")
    assert hits("I need my electrical panel upgraded.") == []


def test_electrical_words_keep_a_message_from_looking_like_spam() -> None:
    message = "Can you look at the outlet in our kitchen? It stopped working."
    plumbing = screening.spam_score("", message, PLUMBING)
    electrical = screening.spam_score("", message, ELECTRICAL)
    assert "no_business_words" in plumbing.signals
    assert "no_business_words" not in electrical.signals


def test_the_electrical_prompt_offers_only_electrical_service_types() -> None:
    prompt = understand.build_system_prompt("2026-10-28T09:00:00+00:00", ELECTRICAL)
    assert "small residential electrical company" in prompt
    assert "drain_cleaning" not in prompt and "water_heater" not in prompt
    schema = understand.json_schema(ELECTRICAL)
    offered = schema["properties"]["fields"]["properties"]["service_type"]["anyOf"][0]["enum"]
    assert offered == [member.value for member in ELECTRICAL.service_types]
    assert ServiceType.drain_cleaning.value not in offered


def test_the_plumbing_schema_offers_only_plumbing_service_types() -> None:
    schema = understand.json_schema()
    offered = schema["properties"]["fields"]["properties"]["service_type"]["anyOf"][0]["enum"]
    assert ServiceType.panel_upgrade.value not in offered


def test_an_electrical_term_name_in_the_message_does_not_block_the_audit_event() -> None:
    from citedesk.events import validate_payload

    message = "I got a shock from the outlet and saw sparks."
    names = hits(message)
    assert "shock" in names
    assert validate_payload({"emergency_hits": names}, protect=[message]) == {
        "emergency_hits": names
    }
