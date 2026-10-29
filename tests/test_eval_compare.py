"""Comparing two settings (thinking on and off) over several passes each.

Runs here are made by hand; no real run and no held-out item is read.
"""

from typing import Any

import pytest

from tests.test_eval_score import escalate, item, reason, record, run_of
from tools import eval_compare as ec
from tools import eval_score as es

GOLDEN = [item(f"i{n}", primary_intent="pricing_question") for n in range(30)] + [
    item(f"e{n}", **escalate("COMPLAINT"), primary_intent="complaint") for n in range(10)
]


def header(thinking: bool, **over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "run_id": "r",
        "split": "tuned",
        "split_sha256": "s" * 64,
        "limit": None,
        "model": "qwen3:8b",
        "prompt_versions": {"understand": "understand-v1", "draft": "draft-v1"},
        "settings": {"enable_thinking": thinking, "spam_threshold": 0.8},
        "git": {"code_tree": "t" * 40, "commit": "c" * 40, "dirty": False},
        "rag": {"chat_model": "qwen3:8b", "thinking": True, "chunks": 83},
    }
    return base | over


def a_pass(
    thinking: bool, wrong_intents: int, missed_escalations: int, **over: Any
) -> dict[str, Any]:
    """A pass in which the first `wrong_intents` plain items are misread and the first
    `missed_escalations` complaints are not escalated."""
    records = []
    for n in range(30):
        wrong = n < wrong_intents
        records.append(
            record(f"i{n}", primary_intent="booking_request" if wrong else "pricing_question")
        )
    for n in range(10):
        if n < missed_escalations:
            records.append(record(f"e{n}", primary_intent="complaint"))
        else:
            records.append(
                record(
                    f"e{n}",
                    status="escalated",
                    route="escalate",
                    primary_intent="complaint",
                    reasons=[reason("COMPLAINT")],
                    draft=None,
                    checks=[],
                )
            )
    run = run_of(*records)
    run["header"] = header(thinking, **over)
    return {"run": run, "vectors": es.item_measures(run, GOLDEN)}


# --- are these runs comparable at all ----------------------------------------------------------


def test_runs_that_differ_only_in_a_setting_are_comparable() -> None:
    a, b = [a_pass(False, 0, 0)], [a_pass(True, 0, 0)]
    assert ec.problems(a, b) == []


@pytest.mark.parametrize(
    ("over", "name"),
    [
        ({"split_sha256": "z" * 64}, "split_sha256"),
        ({"model": "other"}, "model"),
        ({"prompt_versions": {"understand": "understand-v2", "draft": "draft-v1"}}, "prompt"),
        ({"git": {"code_tree": "u" * 40}}, "code_tree"),
        ({"rag": {"chat_model": "x", "chunks": 1}}, "rag"),
        ({"limit": 5}, "limit"),
    ],
)
def test_runs_that_differ_in_anything_but_the_setting_are_refused(
    over: dict[str, Any], name: str
) -> None:
    problems = ec.problems([a_pass(False, 0, 0)], [a_pass(True, 0, 0, **over)])
    assert problems and name in " ".join(problems)


def test_passes_within_one_group_must_be_of_one_system() -> None:
    problems = ec.problems(
        [a_pass(False, 0, 0), a_pass(False, 0, 0, model="other")], [a_pass(True, 0, 0)]
    )
    assert problems and "within" in " ".join(problems)


def test_a_comparison_of_identical_settings_is_flagged() -> None:
    problems = ec.problems([a_pass(False, 0, 0)], [a_pass(False, 0, 0)])
    assert problems and "no setting differs" in " ".join(problems)


def test_the_held_out_split_is_never_used_to_choose_between_settings() -> None:
    a = [a_pass(False, 0, 0, split="heldout")]
    b = [a_pass(True, 0, 0, split="heldout")]
    problems = ec.problems(a, b)
    assert problems and "held-out" in " ".join(problems)


def test_the_setting_that_differs_is_named() -> None:
    assert ec.setting_differences([a_pass(False, 0, 0)], [a_pass(True, 0, 0)]) == {
        "enable_thinking": (False, True)
    }


# --- the comparison ----------------------------------------------------------------------------


def test_a_big_steady_difference_is_called_real() -> None:
    a = [a_pass(False, 2, 1), a_pass(False, 2, 1), a_pass(False, 3, 1)]
    b = [a_pass(True, 12, 6), a_pass(True, 13, 6), a_pass(True, 12, 7)]
    result = ec.compare_groups(a, b, resamples=500)
    row = result["primary_intent"]
    assert row["verdict"]["call"] == "real" and row["verdict"]["higher"] == "a"
    assert row["diff"] > 0.2


def test_no_difference_is_unclear_and_says_how_much_could_have_been_seen() -> None:
    a = [a_pass(False, 4, 2), a_pass(False, 5, 2), a_pass(False, 4, 3)]
    b = [a_pass(True, 4, 2), a_pass(True, 4, 3), a_pass(True, 5, 2)]
    row = ec.compare_groups(a, b, resamples=500)["primary_intent"]
    assert row["verdict"]["call"] == "unclear"
    assert row["verdict"]["smallest_detectable"] > 0


def test_a_single_pass_each_is_unclear_whatever_the_gap() -> None:
    row = ec.compare_groups([a_pass(False, 0, 0)], [a_pass(True, 20, 0)], resamples=300)[
        "primary_intent"
    ]
    assert row["verdict"]["call"] == "unclear"
    assert "two passes" in row["verdict"]["why"]


def test_every_headline_measure_is_compared() -> None:
    result = ec.compare_groups([a_pass(False, 0, 0)], [a_pass(True, 0, 0)], resamples=100)
    assert set(result) == set(es.MEASURES)


# --- the report --------------------------------------------------------------------------------


def test_the_markdown_names_both_settings_and_gives_a_call_per_measure() -> None:
    a = [a_pass(False, 2, 1), a_pass(False, 2, 1)]
    b = [a_pass(True, 12, 6), a_pass(True, 13, 6)]
    text = ec.compare_markdown(
        "think-off", "think-on", a, b, ec.compare_groups(a, b, resamples=200)
    )
    assert "think-off" in text and "think-on" in text and "enable_thinking" in text
    assert "real" in text
    assert "2 passes" in text
    assert "What this cannot tell you" in text


def test_the_markdown_explains_the_rule_for_calling_a_difference_real() -> None:
    a, b = [a_pass(False, 0, 0)], [a_pass(True, 0, 0)]
    text = ec.compare_markdown("a", "b", a, b, ec.compare_groups(a, b, resamples=50))
    assert "bootstrap" in text and "pass" in text
