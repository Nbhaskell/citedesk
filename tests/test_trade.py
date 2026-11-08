"""The trade profile (D-097): everything plumbing-specific comes from one place, and a business of
another trade gets none of it."""

import dataclasses
import json
import re
from pathlib import Path

import pytest

from citedesk import drafting, retrieval, screening, understand
from citedesk.business import Business, load_business
from citedesk.models import ExtractedFields, Intent, ServiceType
from citedesk.trade import PLUMBING, Trade, load_trade, trade_named, trade_of_facts

# An invented trade for the tests only: no plumbing word anywhere in it.
GARDENING = Trade(
    key="gardening",
    company="small garden care company",
    service_type_gloss="other (any garden work), or unknown.",
    service_labels={ServiceType.other: "garden work", ServiceType.unknown: None},
    generic_work="garden work",
    safety_examples="a fallen tree on a house or any other risk to people happening now",
    high_urgency_examples='a fallen branch blocking a drive, "today", or an angry customer',
    emergency_patterns={"fallen_tree": re.compile(r"\btree\b.{0,20}\bfell\b")},
    imaginable=frozenset(),
    business_words=re.compile(r"garden|lawn|hedge|tree"),
)
PLUMBING_WORDS = re.compile(r"plumb|pipe|drain|sewer|water heater|faucet|toilet", re.IGNORECASE)


def facts(tmp_path: Path, trade: str | None) -> Path:
    business = {"name": "Test Co", "phone": "555-0100", "emergency_phone": "555-0101",
                "email": "test@example.com"}  # fmt: skip
    if trade is not None:
        business["trade"] = trade
    path = tmp_path / "facts.json"
    path.write_text(json.dumps({"business": business}), encoding="utf-8")
    return path


def test_a_fact_sheet_without_a_trade_is_plumbing(tmp_path: Path) -> None:
    assert load_trade(facts(tmp_path, None)) is PLUMBING
    assert load_business(facts(tmp_path, None)).trade is PLUMBING


def test_the_named_trade_is_used(tmp_path: Path) -> None:
    assert load_trade(facts(tmp_path, "plumbing")) is PLUMBING


def test_an_unknown_trade_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown trade"):
        load_trade(facts(tmp_path, "astrology"))
    with pytest.raises(ValueError, match="unknown trade"):
        trade_named("astrology")


def test_no_fact_sheet_is_plumbing(tmp_path: Path) -> None:
    assert load_trade(tmp_path / "missing.json") is PLUMBING


def test_the_real_fact_sheet_is_plumbing() -> None:
    assert trade_of_facts(json.loads(Path("universe/facts.json").read_text("utf-8"))) is PLUMBING


def test_every_plumbing_service_type_has_a_label_entry() -> None:
    assert set(PLUMBING.service_types) == set(ServiceType)


def test_the_prompts_of_another_trade_hold_no_plumbing_words() -> None:
    business = dataclasses.replace(
        Business(
            name="Test Co", phone="555-0100", emergency_phone="555-0101", email="test@example.com"
        ),  # fmt: skip
        trade=GARDENING,
    )
    prompts = {
        "understand": understand.build_system_prompt("2026-10-28T09:00:00+00:00", GARDENING),
        "focused": understand.build_focused_prompt(GARDENING),
        "draft": drafting.build_system_prompt(business, 200),
    }
    for name, text in prompts.items():
        assert not PLUMBING_WORDS.search(text), (name, PLUMBING_WORDS.findall(text))
        assert "garden" in text, name


def test_the_plumbing_prompts_still_name_plumbing() -> None:
    assert "small residential plumbing company" in understand.build_system_prompt(
        "2026-10-28T09:00:00+00:00"
    )
    assert "a burst pipe" in understand.build_system_prompt("2026-10-28T09:00:00+00:00")


def test_screening_uses_the_trades_emergency_terms_and_vocabulary() -> None:
    gas = "I smell gas in the kitchen."
    assert screening.screen(None, gas, spam_threshold=0.8).emergency_hits == ["gas_smell"]
    assert screening.screen(None, gas, spam_threshold=0.8, trade=GARDENING).emergency_hits == []
    tree = "A tree fell on the shed."
    outcome = screening.screen(None, tree, spam_threshold=0.8, trade=GARDENING)
    assert outcome.emergency_hits == ["fallen_tree"]
    assert "no_business_words" not in outcome.spam_signals


def test_retrieval_questions_use_the_trades_words() -> None:
    fields = ExtractedFields(**dict.fromkeys(ExtractedFields.model_fields))
    questions = retrieval.build_questions(
        intents=[Intent.booking_request], fields=fields, subject=None, body="Can you come?",
        trade=GARDENING,
    )  # fmt: skip
    assert questions[0].text == "What is needed to book garden work and how does booking work?"
