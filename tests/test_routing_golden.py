"""The routing rules applied to the golden labels (tuned split).

Every item's labels say what should happen. This feeds the labelled intents, fields and reasons to
`decide_route` as if a perfect model had produced them, and checks that code agrees. It tests the
rules, not the model. `NOT_IN_KNOWLEDGE_BASE` is left out because only the knowledge base can
produce it (Phase 5): an item labelled with it routes to a draft here, which is what the rules say
before retrieval.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from citedesk.models import (
    ClassifiedIntent,
    Confidence,
    Intent,
    ReasonCode,
    Route,
    ScreeningResult,
)
from citedesk.routing import MAIN_READING_SIGNALS, decide_route

REPO_ROOT = Path(__file__).resolve().parent.parent
ITEMS: list[dict[str, Any]] = json.loads(
    (REPO_ROOT / "eval/golden/citedesk_v1.json").read_text("utf-8")
)["items"]
NOT_IN_KB = "NOT_IN_KNOWLEDGE_BASE"


def inputs_from_labels(item: dict[str, Any]) -> dict[str, Any]:
    labels = item["labels"]
    reasons = {ReasonCode(code) for code in labels["expected_reason_codes"]}
    if ReasonCode.INJECTION_SUSPECTED in reasons:
        screening = ScreeningResult.injection_suspected
    elif labels["intents"] == ["spam"]:
        screening = ScreeningResult.spam
    else:
        screening = ScreeningResult.clean
    return {
        "intents": [
            ClassifiedIntent(intent=Intent(i), confidence=Confidence.high)
            for i in labels["intents"]
        ],
        "primary_confidence": Confidence.low
        if ReasonCode.LOW_CONFIDENCE in reasons
        else Confidence.high,
        "fields": labels["fields"],
        "signals": sorted(reasons & MAIN_READING_SIGNALS),
        "screening_result": screening,
    }


def expected_before_retrieval(item: dict[str, Any]) -> Route:
    labels = item["labels"]
    if labels["expected_reason_codes"] == [NOT_IN_KB]:
        return Route.draft_reply  # only the knowledge base can decline
    return Route(labels["expected_route"])


@pytest.mark.parametrize("item", ITEMS, ids=[item["id"] for item in ITEMS])
def test_routing_agrees_with_the_label(item: dict[str, Any]) -> None:
    decision = decide_route(**inputs_from_labels(item))
    wanted = {
        ReasonCode(code) for code in item["labels"]["expected_reason_codes"] if code != NOT_IN_KB
    }
    assert set(decision.reason_codes) == wanted
    assert decision.route is expected_before_retrieval(item)


def test_every_route_is_exercised_by_the_set() -> None:
    routes = {decide_route(**inputs_from_labels(item)).route for item in ITEMS}
    assert routes == set(Route)
