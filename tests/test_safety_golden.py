"""The emergency net against the labelled golden set (tuned split).

The net was extended with these messages in view (D-037), so this shows the machinery agrees with
the labels on them, not how it generalises; the held-out set is the honest test. Before the
extension the net missed one safety item and fired on two ordinary ones.
"""

from typing import Any

from citedesk.safety import emergency_hits
from tests.golden_data import tuned_golden

ITEMS: list[dict[str, Any]] = tuned_golden()["items"]

# Fires on "flooded my kitchen" in a legal threat about a repair that failed days earlier. Nothing
# in the clause says it is over, so the net cannot tell; the item escalates anyway (LEGAL_THREAT).
KNOWN_OVER_FIRES = {"legal-sue-over-water-damage"}


def fired(item: dict[str, Any]) -> bool:
    return bool(emergency_hits(f"{item.get('subject') or ''}\n{item['body']}"))


def is_safety(item: dict[str, Any]) -> bool:
    return "HEALTH_SAFETY" in item["labels"]["expected_reason_codes"]


def test_the_net_misses_no_safety_item() -> None:
    missed = [item["id"] for item in ITEMS if is_safety(item) and not fired(item)]
    assert missed == []


def test_the_net_fires_on_nothing_else_but_the_known_over_fire() -> None:
    extra = {item["id"] for item in ITEMS if fired(item) and not is_safety(item)}
    assert extra == KNOWN_OVER_FIRES


def test_there_are_safety_items_to_miss() -> None:
    assert sum(is_safety(item) for item in ITEMS) == 8
