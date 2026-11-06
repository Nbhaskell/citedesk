"""The development-set scorer for the exception signal (D-074). No model is used."""

from typing import Any

from tools import dev_signals


def items() -> list[dict[str, Any]]:
    return [
        {"id": "p1", "expect_exception": True, "body": "x"},
        {"id": "p2", "expect_exception": True, "body": "x"},
        {"id": "n1", "expect_exception": False, "body": "x"},
        {"id": "n2", "expect_exception": False, "body": "x"},
    ]


def test_scoring_counts_recall_and_false_alarms_and_names_the_ids() -> None:
    flagged = {"p1": True, "p2": False, "n1": True, "n2": False}
    result = dev_signals.score(items(), flagged)
    assert (result["caught"], result["positives"]) == (1, 2)
    assert (result["false_alarms"], result["negatives"]) == (1, 2)
    assert result["missed_ids"] == ["p2"]
    assert result["false_alarm_ids"] == ["n1"]


def test_the_rendered_summary_never_holds_the_message_text() -> None:
    rows = [{**i, "body": "PRIVATE WORDS"} for i in items()]
    text = dev_signals.render(dev_signals.score(rows, {"p1": True}), "focused question")
    assert "PRIVATE WORDS" not in text
    assert "focused question" in text


def test_the_development_file_is_valid_and_has_both_kinds() -> None:
    loaded = dev_signals.load_items(dev_signals.DEFAULT_FILE)
    assert len({i["id"] for i in loaded}) == len(loaded)
    assert sum(i["expect_exception"] for i in loaded) >= 15
    assert sum(not i["expect_exception"] for i in loaded) >= 15
