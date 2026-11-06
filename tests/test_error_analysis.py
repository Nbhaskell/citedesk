"""The error-analysis tool reads saved runs and labels. It needs no model."""

from typing import Any

from tools import error_analysis as ea


def gold(
    item_id: str, primary: str, route: str, reasons: list[str], category: str
) -> dict[str, Any]:
    return {
        "id": item_id,
        "category": category,
        "labels": {
            "primary_intent": primary,
            "expected_route": route,
            "expected_reason_codes": reasons,
        },
    }


def got(item_id: str, primary: str | None, route: str) -> dict[str, Any]:
    return {"id": item_id, "primary_intent": primary, "route": route, "reasons": []}


GOLD = [
    gold("a", "service_question", "draft_reply", [], "routine_answerable"),
    gold("b", "billing_question", "escalate", ["REFUND_OR_DISPUTE"], "dispute_legal"),
    gold("c", "spam", "archive", [], "spam"),
]
PASS_1 = [
    got("a", "availability_question", "request_details"),
    got("b", "complaint", "escalate"),
    got("c", "spam", "archive"),
]
PASS_2 = [
    got("a", "availability_question", "request_details"),
    got("b", "complaint", "escalate"),
    got("c", "spam", "archive"),
]


def test_the_confusion_counts_only_wrong_pairs_across_passes() -> None:
    result = ea.analyse(GOLD, [PASS_1, PASS_2])
    assert result["confusion"][("service_question", "availability_question")] == 2
    assert result["confusion"][("billing_question", "complaint")] == 2
    assert ("spam", "spam") not in result["confusion"]


def test_a_miss_that_also_changes_the_route_is_told_apart_from_one_that_does_not() -> None:
    result = ea.analyse(GOLD, [PASS_1, PASS_2])
    by_id = {m["id"]: m for m in result["misses"]}
    assert set(by_id) == {"a", "b"}
    assert by_id["a"]["route_wrong"] is True
    assert by_id["b"]["route_wrong"] is False


def test_an_unread_item_has_no_prediction_and_is_counted() -> None:
    unread = [
        got("a", None, "escalate"),
        got("b", "billing_question", "escalate"),
        got("c", "spam", "archive"),
    ]
    result = ea.analyse(GOLD, [unread])
    assert result["confusion"][("service_question", "(not read)")] == 1


def test_the_report_has_ids_and_labels_and_never_message_text() -> None:
    gold_items = [{**g, "body": "SECRET MESSAGE TEXT"} for g in GOLD]
    text = ea.render(ea.analyse(gold_items, [PASS_1, PASS_2]), passes=2)
    assert "service_question" in text
    assert "SECRET MESSAGE TEXT" not in text
