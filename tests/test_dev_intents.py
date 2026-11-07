"""The development-set scorer for the primary intent (D-085). No model is used."""

from typing import Any

from tools import dev_intents


def items() -> list[dict[str, Any]]:
    return [
        {"id": "h1", "expect_primary": "service_question", "body": "x"},
        {"id": "h2", "expect_primary": "service_question", "body": "x"},
        {"id": "a1", "expect_primary": "availability_question", "body": "x"},
        {"id": "a2", "expect_primary": "availability_question", "body": "x"},
    ]


def test_scoring_counts_hits_and_names_what_each_miss_was_read_as() -> None:
    read = {"h1": "service_question", "h2": "availability_question", "a1": "availability_question"}
    result = dev_intents.score(items(), read)
    assert (result["correct"], result["total"]) == (2, 4)
    assert result["misses"] == {"h2": "availability_question", "a2": None}
    assert result["by_expected"]["service_question"] == {"correct": 1, "total": 2}
    assert result["by_expected"]["availability_question"] == {"correct": 1, "total": 2}


def test_the_rendered_summary_never_holds_the_message_text() -> None:
    rows = [{**i, "body": "PRIVATE WORDS"} for i in items()]
    text = dev_intents.render(dev_intents.score(rows, {"h1": "service_question"}), "main reading")
    assert "PRIVATE WORDS" not in text
    assert "main reading" in text
    assert "a2: not read" in text


def test_the_hours_and_availability_file_is_valid_and_has_both_kinds() -> None:
    loaded = dev_intents.load_items(dev_intents.SETS["hours"])
    assert len({i["id"] for i in loaded}) == len(loaded)
    kinds = [i["expect_primary"] for i in loaded]
    assert kinds.count("service_question") >= 12
    assert kinds.count("availability_question") >= 12


def test_the_spam_file_is_valid_and_has_the_three_kinds() -> None:
    loaded = dev_intents.load_items(dev_intents.SETS["spam"])
    assert len({i["id"] for i in loaded}) == len(loaded)
    kinds = [i["expect_primary"] for i in loaded]
    assert kinds.count("spam") >= 10
    assert kinds.count("partnership_or_sales") >= 6
    assert kinds.count("billing_question") >= 3
