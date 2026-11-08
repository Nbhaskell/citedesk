"""The trade a business works in: everything in the code that belongs to plumbing and not to every
small service business (D-097).

A trade gives the words the prompts use for the business and its work, the service types and how a
question about each is worded, the examples of an emergency, the emergency terms the safety net
looks for, and the words that make a message look like it comes from a customer. Code still decides
everything; a trade only supplies the vocabulary.

The trade is named in the fact sheet (`business.trade`); a fact sheet without one is plumbing, the
trade Citedesk was built for.
"""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from citedesk.models import ServiceType
from citedesk.safety import EMERGENCY_PATTERNS, IMAGINABLE


@dataclass(frozen=True)
class Trade:
    key: str
    # "You read one customer message sent to a {company}"
    company: str
    # The fields line of the understand prompt, after "- service_type: "
    service_type_gloss: str
    # How a question to the knowledge base names each service type; None asks generally.
    service_labels: Mapping[ServiceType, str | None]
    # The booking question when no service type is known: "What is needed to book {generic_work}"
    generic_work: str
    # The health_or_safety intent, after "- health_or_safety: "
    safety_examples: str
    # The high urgency examples, after "- high: cannot wait, such as "
    high_urgency_examples: str
    emergency_patterns: Mapping[str, re.Pattern[str]]
    # Emergency terms discounted when only imagined ("if a pipe bursts ..."), D-085
    imaginable: frozenset[str]
    # Words that make a message look like it comes from a customer, for the spam score
    business_words: re.Pattern[str]

    @property
    def service_types(self) -> tuple[ServiceType, ...]:
        return tuple(self.service_labels)


PLUMBING = Trade(
    key="plumbing",
    company="small residential plumbing company",
    service_type_gloss=(
        "emergency_repair (an emergency call-out), drain_cleaning (clogged or slow drains, "
        "sewer line cleaning), leak_repair (finding or fixing a leak), sewer_line_repair, "
        "water_heater, fixture_installation (taps, toilets, sinks, shower fittings), inspection, "
        "other (any other plumbing work), or unknown."
    ),
    service_labels={
        ServiceType.emergency_repair: "emergency plumbing repair",
        ServiceType.drain_cleaning: "drain cleaning",
        ServiceType.leak_repair: "leak repair",
        ServiceType.sewer_line_repair: "sewer line repair",
        ServiceType.water_heater: "water heater service or replacement",
        ServiceType.fixture_installation: "fixture installation",
        ServiceType.inspection: "plumbing inspection",
        ServiceType.other: "plumbing repair",
        ServiceType.unknown: None,
    },
    generic_work="plumbing work",
    safety_examples=(
        "a gas smell, carbon monoxide, flooding, a burst pipe, sewage coming up, water near "
        "electrics, or any other risk to people or property that is happening now"
    ),
    high_urgency_examples=(
        'no hot water, a leak getting worse, "as soon as possible", "today", or an angry customer'
    ),
    emergency_patterns=EMERGENCY_PATTERNS,
    imaginable=IMAGINABLE,
    # Plumbing and service vocabulary only. Words such as price, cost, quote or book also appear
    # in spam, so they would hide the "no business words" signal.
    business_words=re.compile(
        r"plumb|drain|leak|toilet|water|pipe|sink|faucet|\btap\b|heater|sewer|shower|\btub\b|bath|"
        r"clog|flood|\bgas\b|\bhot\b|overflow|repair|install|appointment|warranty|invoice|receipt|"
        r"emergency"
    ),
)

TRADES: Mapping[str, Trade] = {PLUMBING.key: PLUMBING}


def trade_named(key: str) -> Trade:
    try:
        return TRADES[key]
    except KeyError:
        raise ValueError(f"unknown trade {key!r}; known: {', '.join(sorted(TRADES))}") from None


def trade_of_facts(data: Mapping[str, Any]) -> Trade:
    """The trade a fact sheet names, or plumbing when it names none."""
    return trade_named(str(data.get("business", {}).get("trade") or PLUMBING.key))


def load_trade(path: Path) -> Trade:
    """The trade of the fact sheet at `path`. Without a fact sheet, plumbing: screening and reading
    a message do not need one, and worked before trades existed."""
    if not path.is_file():
        return PLUMBING
    return trade_of_facts(json.loads(path.read_text("utf-8")))
