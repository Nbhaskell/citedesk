"""The intent baseline that uses no model (tools/intent_baseline.py, D-093).

All items here are invented fixtures built in the tests. No test reads the real golden set.
"""

import json
from pathlib import Path

import pytest

from tools import intent_baseline as ib


def item(item_id: str, primary: str, body: str, split: str = "tuned") -> dict:
    return {
        "id": item_id,
        "split": split,
        "subject": "",
        "body": body,
        "labels": {"primary_intent": primary},
    }


TRAIN = [
    item("p1", "pricing_question", "how much does drain cleaning cost"),
    item("p2", "pricing_question", "what is the price to clear a drain"),
    item("p3", "pricing_question", "how much for a water heater flush"),
    item("b1", "booking_request", "please book a visit for friday"),
    item("b2", "booking_request", "can you come out to fix my tap"),
    item("s1", "spam", "buy cheap followers now limited offer"),
]


def test_words_are_lower_case_with_pairs_of_neighbours() -> None:
    assert ib.features("How much, HOW much?") == [
        "how", "much", "how", "much", "how much", "much how", "how much",
    ]  # fmt: skip


def test_the_majority_baseline_always_answers_the_commonest_intent() -> None:
    model = ib.Majority.fit(TRAIN)
    assert model.predict("anything at all") == "pricing_question"


def test_naive_bayes_learns_the_words_of_each_intent() -> None:
    model = ib.NaiveBayes.fit(TRAIN)
    assert model.predict("how much would it cost to clean the drain") == "pricing_question"
    assert model.predict("could you come on friday for a visit") == "booking_request"
    assert model.predict("limited offer buy followers") == "spam"


def test_naive_bayes_with_no_known_words_falls_back_to_the_priors() -> None:
    model = ib.NaiveBayes.fit(TRAIN)
    assert model.predict("zzz qqq") == "pricing_question"


def test_the_same_data_gives_the_same_answers() -> None:
    first = ib.NaiveBayes.fit(TRAIN)
    second = ib.NaiveBayes.fit(list(reversed(TRAIN)))
    for text in ("how much", "book friday", "offer", "hello"):
        assert first.predict(text) == second.predict(text)


def test_wilson_interval() -> None:
    low, high = ib.wilson(52, 75)
    assert 0.58 < low < 0.60 and 0.78 < high < 0.80
    assert ib.wilson(0, 0) == (None, None)


def test_scoring_counts_hits_and_lists_the_confusions() -> None:
    test = [
        item("t1", "pricing_question", "how much to clean a drain", "heldout"),
        item("t2", "spam", "can you come and book a visit", "heldout"),
    ]
    result = ib.evaluate(ib.NaiveBayes.fit(TRAIN), test)
    assert result["n"] == 2 and result["correct"] == 1
    assert result["confusion"] == {"spam -> booking_request": 1}
    assert result["predictions"] == {"t1": "pricing_question", "t2": "booking_request"}


def test_leave_one_out_never_scores_an_item_it_was_trained_on() -> None:
    seen: list[set[str]] = []

    class Spy:
        def __init__(self, ids: set[str]) -> None:
            self.ids = ids

        @classmethod
        def fit(cls, items: list[dict]) -> "Spy":
            spy = cls({i["id"] for i in items})
            seen.append(spy.ids)
            return spy

        def predict(self, text: str) -> str:
            return "pricing_question"

    result = ib.leave_one_out(Spy, TRAIN)
    all_ids = {i["id"] for i in TRAIN}
    assert result["n"] == len(TRAIN)
    assert all(len(ids) == len(TRAIN) - 1 for ids in seen)
    assert {next(iter(all_ids - ids)) for ids in seen} == all_ids


def test_paired_comparison_with_a_model_run() -> None:
    gold = {"a": "spam", "b": "other", "c": "complaint", "d": "spam"}
    baseline = {"a": "spam", "b": "spam", "c": "complaint", "d": "other"}
    model = {"a": "spam", "b": "other", "c": "other"}  # d was not read by the model
    paired = ib.paired(gold, baseline, model)
    assert paired == {
        "n": 3,
        "both_right": 1,
        "model_only": 1,
        "baseline_only": 1,
        "both_wrong": 0,
        "model_correct": 2,
        "baseline_correct": 2,
    }


def test_a_sealed_item_is_refused() -> None:
    with pytest.raises(ValueError, match="sealed"):
        ib.split_items([*TRAIN, item("x", "spam", "x", split="sealed")])


def test_the_report_holds_ids_and_counts_but_no_message_text(tmp_path: Path) -> None:
    marker = "UNIQUE-MESSAGE-WORDS-12345"
    items = [
        *TRAIN,
        item("h1", "pricing_question", f"how much {marker}", "heldout"),
        item("h2", "spam", f"cheap offer {marker}", "heldout"),
    ]
    golden = tmp_path / "golden.json"
    golden.write_text(json.dumps({"header": {}, "items": items}), encoding="utf-8")
    report = tmp_path / "report.md"
    assert ib.main(["--golden", str(golden), "--md", str(report)]) == 0
    text = report.read_text(encoding="utf-8")
    assert marker not in text
    assert "Naive Bayes" in text and "Majority" in text
