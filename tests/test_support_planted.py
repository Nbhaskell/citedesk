"""How often the review aids point at a planted sentence (D-077), on a development set.

Each planted sentence is added to an ordinary draft built from fixed sources. This is a guard
against the marker getting worse; the claim about reviewers is made only by rerunning the trial.
"""

import json
from pathlib import Path

import pytest

from citedesk import support
from citedesk.models import Source

REPO_ROOT = Path(__file__).resolve().parent.parent
PLANTS = json.loads((REPO_ROOT / "eval/dev/planted_sentences_dev.json").read_text("utf-8"))["items"]

SOURCES = [
    Source(
        file="pricing.md",
        section="Pricing > Drain cleaning",
        page=None,
        text="- Drain cleaning, one fixture (sink, tub, shower or toilet): $149 (starting price)\n"
        "- Main sewer line cleaning: $329",
    ),
    Source(
        file="pricing.md",
        section="Pricing > Leak detection",
        page=None,
        text="- Leak detection (electronic, finds the source of a hidden leak): $245. Credited "
        "toward the repair if the customer approves it during the same visit.",
    ),
    Source(
        file="policies.md",
        section="Policies > Warranty and cancelling",
        page=None,
        text="Repairs carry a 90-day workmanship warranty on labour. Cancelling with less than "
        "24 hours notice is charged the call-out fee.",
    ),
]
ORDINARY = (
    "Drain cleaning for one fixture starts at $149.",
    "A member of our team will confirm the details.",
)
ASK = "How much to clear my kitchen sink drain?"


def flagged(sentence: str) -> bool:
    body = "\n\n".join(["Hi Cecily,", ORDINARY[0], sentence, ORDINARY[1], "Kind regards,\nKH"])
    result = support.analyse(body, SOURCES, ASK)
    unsupported = any(s.text == sentence and s.status == "unsupported" for s in result.sentences)
    return unsupported or any(f.mismatch for f in result.figures)


def test_the_ordinary_sentences_alone_raise_nothing() -> None:
    body = "\n\n".join(["Hi Cecily,", *ORDINARY, "Kind regards,\nKH"])
    result = support.analyse(body, SOURCES, ASK)
    assert all(s.status != "unsupported" for s in result.sentences)
    assert not any(f.mismatch for f in result.figures)


def test_most_planted_sentences_are_pointed_at() -> None:
    missed = [p["id"] for p in PLANTS if not flagged(p["sentence"])]
    assert len(missed) <= 3, f"not flagged: {missed}"


@pytest.mark.parametrize("kind", sorted({p["kind"] for p in PLANTS}))
def test_every_kind_is_pointed_at_at_least_four_times_in_five(kind: str) -> None:
    sentences = [p["sentence"] for p in PLANTS if p["kind"] == kind]
    assert sum(flagged(s) for s in sentences) >= 4, kind
