"""Emergency terms: a keyword net in code, so no model is needed to notice an emergency.

Phase 3 uses it for two things only: spam is never archived when an emergency term is present, and
an inquiry escalated for suspected injection still gets the `HEALTH_SAFETY` reason and urgent
priority, because no model reads it. Phase 4 builds the full safety net on top (raising urgency
for model-classified inquiries) and measures it on the golden set.

Hits are pattern names, never the matched text.
"""

import re

from citedesk.textnorm import normalise

EMERGENCY_PATTERNS: dict[str, re.Pattern[str]] = {
    "gas_smell": re.compile(
        r"\b(?:smell|smells|smelled|smelling|odou?r)\b.{0,25}\bgas\b"
        r"|\bgas\b.{0,12}\b(?:smell|smells|odou?r|leak|leaks|leaking)\b"
        r"|\brotten eggs?\b"
    ),
    "carbon_monoxide": re.compile(r"\bcarbon monoxide\b|\bco\b\s*(?:alarms?|detectors?)\b"),
    "flooding": re.compile(
        r"\bflood(?:s|ed|ing)?\b"
        r"|\bwater\b.{0,15}\b(?:everywhere|pouring|gushing)\b"
        r"|\beverywhere\b.{0,10}\bwater\b"
    ),
    "burst_pipe": re.compile(
        r"\bburst\b.{0,20}\bpipes?\b|\bpipes?\b.{0,20}\bburst\b|\bbursting\b.{0,20}\bpipes?\b"
    ),
    "sewage": re.compile(
        r"\bsewage\b|\bsewer\b.{0,20}\b(?:back(?:ing|ed)?\s*up|backup)\b|\bbacking up into\b"
    ),
    "electrical": re.compile(
        r"\bsparks?\b|\bsparking\b|\belectric(?:al)? shock\b"
        r"|\b(?:electrical|breaker|fuse)\s*(?:panel|box)\b"
    ),
}


def emergency_hits(text: str) -> list[str]:
    """Names of the emergency patterns found in the text, in a stable order."""
    normalised = normalise(text)
    return [name for name, pattern in EMERGENCY_PATTERNS.items() if pattern.search(normalised)]


def has_emergency_terms(text: str) -> bool:
    return bool(emergency_hits(text))
