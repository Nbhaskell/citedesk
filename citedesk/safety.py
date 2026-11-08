"""Emergency terms: a keyword net in code, so no model is needed to notice an emergency.

Used three ways: spam is never archived when an emergency term is present; an inquiry escalated
for suspected injection still gets the `HEALTH_SAFETY` reason and urgent priority, because no model
reads it; and for every other inquiry the understand stage raises urgency and the route stage adds
`HEALTH_SAFETY` when the net fires, even if the model missed it (docs/TRD.md section 4.2).

The net errs towards firing: a missed emergency costs far more than an extra look from the owner.
Two additions keep it honest (D-037): sewage is also recognised when it is described rather than
named, and a mention is discounted when its own clause says it was long ago. Hits are pattern
names, never the matched text.
"""

import re
from collections.abc import Mapping

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
        # Described rather than named: foul water on a floor, toilet paper where it should not be,
        # water coming up out of a drain, a toilet that overflows.
        r"|\b(?:dirty|smelly|smelling|foul|filthy|stinky|stinking|brown|black|grey|gray|murky)\b"
        r"[^.!?]{0,25}\bwater\b[^.!?]{0,60}\b(?:on|across|over)\b[^.!?]{0,25}\bfloor\b"
        r"|\btoilet paper\b[^.!?]{0,40}\b(?:floor|tub|shower|sink|drain)\b"
        r"|\b(?:floor|tub|shower|sink)\b[^.!?]{0,40}\btoilet paper\b"
        r"|\b(?:coming|comes|came|bubbling|bubbles|bubbled|rising|rises|rose|welling)\s+up\s+"
        r"(?:out\s+of|through|from)\s+(?:the\s+|our\s+|my\s+)?(?:floor\s+drain|toilet|tub|shower)\b"
        r"|\btoilet\b[^.!?]{0,15}\boverflow(?:s|ed|ing)\b"
    ),
    "electrical": re.compile(
        r"\bsparks?\b|\bsparking\b|\belectric(?:al)? shock\b"
        r"|\b(?:electrical|breaker|fuse)\s*(?:panel|box)\b"
    ),
}

# The electrical trade (D-098). Gas and carbon monoxide are kept: any customer may report them.
# A breaker panel or a fuse box named on its own is not an emergency here, because an electrician
# is asked about panels every day; what makes one an emergency is a sign of heat, fire or shock.
ELECTRICAL_EMERGENCY_PATTERNS: dict[str, re.Pattern[str]] = {
    "gas_smell": EMERGENCY_PATTERNS["gas_smell"],
    "carbon_monoxide": EMERGENCY_PATTERNS["carbon_monoxide"],
    "burning_smell": re.compile(
        r"\b(?:burning|melting|scorched?|singed)\b.{0,15}\b(?:smell|smells|odou?r|plastic)\b"
        r"|\b(?:smell|smells|smelled|odou?r)\b.{0,15}\b(?:burning|melting|scorched?)\b"
    ),
    "sparks_or_smoke": re.compile(
        r"\bspark(?:s|ed|ing|y)?\b|\barc(?:ing|ed)\b"
        r"|\bsmoke\b.{0,20}\b(?:from|out of|coming)\b.{0,25}"
        r"\b(?:outlet|socket|switch|panel|breaker|wall|light|fixture|plug|wire|wiring)s?\b"
        r"|\b(?:on fire|caught fire|flames?)\b"
    ),
    "shock": re.compile(
        # "shocked at the price" is not a shock: a person must get one, or it must be electric
        r"\belectric(?:al)?\s+shocks?\b"
        r"|\b(?:got|get|gets|getting|gave me|giving|felt)\s+(?:a\s+)?(?:\w+\s+)?shocks?\b"
        r"|\bshocks?\s+(?:from|when|off)\b|\belectrocut\w*\b|\bgot a (?:jolt|zap)\b"
    ),
    "exposed_wires": re.compile(
        r"\b(?:exposed|bare|live|loose|dangling|hanging)\b.{0,10}\bwir(?:e|es|ing)\b"
    ),
    "hot_fitting": re.compile(
        r"\b(?:outlet|socket|switch|plug|panel|breaker)s?\b.{0,25}"
        # "the breaker for the hot tub" is not a hot breaker
        r"\b(?:(?:is|are|feels?|getting|gets|too|very|really)\s+hot|hot to the touch|warm to the "
        r"touch|melted|melting|scorched|blackened|buzzing)\b"
    ),
    "downed_line": re.compile(
        r"\b(?:power|electric(?:al)?|utility)\s+lines?\b.{0,20}\b(?:down|fell|fallen|ground)\b"
        r"|\bdowned\s+(?:power\s+)?lines?\b"
    ),
    "water_and_electrics": re.compile(
        r"\bwater\b.{0,30}\b(?:outlet|socket|panel|breaker|wiring|light fixture)s?\b"
        r"|\b(?:outlet|socket|panel|breaker|wiring)s?\b.{0,30}\b(?:wet|soaked|flooded)\b"
    ),
}

# A mention of an emergency is discounted when its own clause says it was long ago ("a pipe burst in
# our kitchen last month") and does not also say it is happening again. The window is one clause,
# so "last year ... please help, water everywhere" still fires on the second half.
CLAUSE_BREAK = re.compile(r"[.!?;,]+|\b(?:and|but|so|because|now|please|then)\b")
HISTORICAL = re.compile(
    r"\blast (?:month|year|winter|summer|spring|fall|autumn)\b"
    r"|\b(?:months?|years?) ago\b"
    r"|\bback in\b"
    r"|\bin (?:19|20)\d\d\b"
    r"|\bthe last time\b"
    r"|\bpreviously\b"
)
PRESENT = re.compile(
    r"\b(?:again|still|today|tonight|currently|this (?:morning|afternoon|evening))\b"
)


def _is_history(text: str, match: re.Match[str], breaks: list[tuple[int, int]]) -> bool:
    start = max((end for begin, end in breaks if end <= match.start()), default=0)
    stop = min((begin for begin, _ in breaks if begin >= match.end()), default=len(text))
    clause = text[start:stop]
    return bool(HISTORICAL.search(clause)) and not PRESENT.search(clause)


# A water event that is only imagined ("if a pipe bursts at night, do you come out?", D-085). The
# cue must sit right before the term in its own clause, and nothing in the clause may say it is
# happening. Gas, carbon monoxide and electrical terms are never discounted this way: a customer
# who asks what to do if they smell gas should still be looked at.
HYPOTHETICAL = re.compile(r"\b(?:if|in case(?: of)?|what if|suppose|supposing)\b[^.!?;,]{0,28}$")
IMAGINABLE = frozenset({"flooding", "burst_pipe", "sewage"})


def _is_imagined(text: str, match: re.Match[str], breaks: list[tuple[int, int]]) -> bool:
    start = max((end for begin, end in breaks if end <= match.start()), default=0)
    stop = min((begin for begin, _ in breaks if begin >= match.end()), default=len(text))
    return bool(HYPOTHETICAL.search(text[start : match.start()])) and not PRESENT.search(
        text[start:stop]
    )


def _fires(
    name: str,
    pattern: re.Pattern[str],
    text: str,
    breaks: list[tuple[int, int]],
    imaginable: frozenset[str] = IMAGINABLE,
) -> bool:
    """True if any match of the pattern, overlapping ones included, is neither past history nor
    (for water events) imagined."""
    position = 0
    while (match := pattern.search(text, position)) is not None:
        if not _is_history(text, match, breaks) and not (
            name in imaginable and _is_imagined(text, match, breaks)
        ):
            return True
        position = match.start() + 1
    return False


def emergency_hits(
    text: str,
    patterns: Mapping[str, re.Pattern[str]] | None = None,
    imaginable: frozenset[str] = IMAGINABLE,
) -> list[str]:
    """Names of the emergency patterns found in the text, in a stable order. The patterns are a
    trade's (D-097); without them, the plumbing ones below."""
    normalised = normalise(text)
    breaks = [(m.start(), m.end()) for m in CLAUSE_BREAK.finditer(normalised)]
    return [
        name
        for name, pattern in (EMERGENCY_PATTERNS if patterns is None else patterns).items()
        if _fires(name, pattern, normalised, breaks, imaginable)
    ]


def has_emergency_terms(
    text: str,
    patterns: Mapping[str, re.Pattern[str]] | None = None,
    imaginable: frozenset[str] = IMAGINABLE,
) -> bool:
    return bool(emergency_hits(text, patterns, imaginable))
