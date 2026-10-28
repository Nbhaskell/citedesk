import pytest

from citedesk.safety import emergency_hits, has_emergency_terms


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("i think i smell gas in the basement", "gas_smell"),
        ("There is a strong gas smell near the stove", "gas_smell"),
        ("faint rotten egg smell near our stove", "gas_smell"),
        ("we have a gas leak", "gas_smell"),
        ("our carbon monoxide detector went off", "carbon_monoxide"),
        ("the CO alarm is beeping", "carbon_monoxide"),
        ("BASEMENT IS FLOODING FAST", "flooding"),
        ("the kitchen flooded overnight", "flooding"),
        ("water everywhere in the hallway", "flooding"),
        ("a pipe burst in the kitchen wall", "burst_pipe"),
        ("we have a burst pipe", "burst_pipe"),
        ("sewage is coming up through the drain", "sewage"),
        ("the sewer is backing up into the house", "sewage"),
        ("a pipe is dripping onto our electrical panel", "electrical"),
        ("I saw sparks from the outlet near the leak", "electrical"),
        ("water on the fuse box and it is buzzing", "electrical"),
    ],
)
def test_emergency_terms_are_found(text: str, expected: str) -> None:
    assert expected in emergency_hits(text)
    assert has_emergency_terms(text)


@pytest.mark.parametrize(
    "text",
    [
        "how much does drain cleaning cost",
        "our current water heater is gas, can you replace it with another gas one",
        "we have a gas stove and a gas dryer",
        "we are redoing the flooring in the kitchen",
        "a burst of cold air came from the vent",
        "I need the carbon filter changed",
        "the water heater is making a loud banging noise",
        "my sump pump runs a lot",
        "please ignore my earlier message about the date",
        "",
    ],
)
def test_ordinary_messages_have_no_emergency_terms(text: str) -> None:
    assert emergency_hits(text) == []
    assert not has_emergency_terms(text)


def test_matching_ignores_case_and_odd_spacing() -> None:
    assert has_emergency_terms("I   SMELL    GAS!!")
    assert has_emergency_terms("Burst\nPipe")


def test_zero_width_characters_do_not_hide_a_term() -> None:
    assert has_emergency_terms("sm​ell ga​s")


def test_hits_are_names_not_text() -> None:
    hits = emergency_hits("sewage coming up and I smell gas")
    assert set(hits) == {"gas_smell", "sewage"}
    assert all(h.isidentifier() for h in hits)
