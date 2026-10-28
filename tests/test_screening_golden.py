"""The screening detectors against the labelled golden set (tuned split).

The detectors were written with these messages in view, so a pass shows the machinery works on
them, not how it generalises. The held-out set, written after the prototype exists, is the
honest test. Failures list every mismatching item id, not just the first.
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from citedesk.models import ScreeningResult
from citedesk.screening import screen

REPO_ROOT = Path(__file__).resolve().parent.parent
ITEMS: list[dict[str, Any]] = json.loads(
    (REPO_ROOT / "eval/golden/citedesk_v1.json").read_text("utf-8")
)["items"]
THRESHOLD = 0.8


def expected_result(item: dict[str, Any]) -> ScreeningResult:
    labels = item["labels"]
    if "INJECTION_SUSPECTED" in labels["expected_reason_codes"]:
        return ScreeningResult.injection_suspected
    if labels["intents"] == ["spam"]:
        return ScreeningResult.spam
    return ScreeningResult.clean


def outcome(item: dict[str, Any]) -> Any:
    return screen(item.get("subject"), item["body"], spam_threshold=THRESHOLD)


def test_every_item_gets_the_result_its_label_implies() -> None:
    wrong = [
        f"{item['id']}: expected {expected_result(item).value}, got {outcome(item).result.value}"
        for item in ITEMS
        if outcome(item).result is not expected_result(item)
    ]
    assert wrong == []


def test_no_real_inquiry_is_archived_as_spam() -> None:
    archived = [
        item["id"]
        for item in ITEMS
        if outcome(item).result is ScreeningResult.spam and item["labels"]["intents"] != ["spam"]
    ]
    assert archived == []


def test_no_emergency_item_is_archived_or_held_back_as_spam_or_injection() -> None:
    risky = [
        item["id"]
        for item in ITEMS
        if "HEALTH_SAFETY" in item["labels"]["expected_reason_codes"]
        and outcome(item).result is not ScreeningResult.clean
    ]
    assert risky == []


def test_exactly_the_labelled_injection_items_are_flagged() -> None:
    flagged = {item["id"] for item in ITEMS if outcome(item).injection_flags}
    labelled = {
        item["id"]
        for item in ITEMS
        if "INJECTION_SUSPECTED" in item["labels"]["expected_reason_codes"]
    }
    assert flagged == labelled


def test_the_labelled_near_misses_are_not_flagged_or_masked() -> None:
    near_misses = [item for item in ITEMS if item["category"] == "near_miss"]
    assert len(near_misses) == 4
    for item in near_misses:
        result = outcome(item)
        assert result.injection_flags == [], item["id"]
        assert result.sensitive_kinds == [], item["id"]
        assert result.body == item["body"], item["id"]
        assert result.subject == item["subject"], item["id"]


def test_sensitive_data_is_masked_exactly_where_labelled() -> None:
    masked = {item["id"] for item in ITEMS if outcome(item).sensitive_kinds}
    labelled = {item["id"] for item in ITEMS if item["labels"].get("contains_sensitive_data")}
    assert masked == labelled == {"edge-card-number-in-message"}


def test_the_stored_text_never_contains_the_original_card_number() -> None:
    item = next(i for i in ITEMS if i["id"] == "edge-card-number-in-message")
    result = outcome(item)
    digits_in_body = re.sub(r"\D", "", result.body)
    assert "4111111111111111" not in digits_in_body
    assert "411111111111" not in digits_in_body
    assert "**** **** **** 1111" in result.body
    assert "09/28" in result.body  # the rest of the message is untouched


def test_spam_scores_separate_the_two_groups_with_room_to_spare() -> None:
    spam = [outcome(i).spam_score for i in ITEMS if i["labels"]["intents"] == ["spam"]]
    other = [outcome(i).spam_score for i in ITEMS if i["labels"]["intents"] != ["spam"]]
    assert min(spam) >= THRESHOLD
    assert max(other) < THRESHOLD
    # Report the margin so a future change that closes it is noticed.
    assert max(other) <= 0.5, f"highest score among real inquiries is {max(other)}"


@pytest.mark.parametrize("item", ITEMS, ids=[i["id"] for i in ITEMS])
def test_screening_does_not_change_an_ordinary_message(item: dict[str, Any]) -> None:
    result = outcome(item)
    if not result.sensitive_kinds:
        assert result.body == item["body"]
        assert result.subject == item.get("subject")
