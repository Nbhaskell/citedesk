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

# The parts of an electrical system a customer names (D-106). Used on both sides of a symptom,
# so "the dimmer gets hot" and "smoke came out of the fan motor" are both found.
_PARTS = (
    r"\b(?:outlets?|sockets?|receptacles?|(?:light |dimmer )?switch(?:es)?|switch plates?|dimmers?|"
    r"plugs?|cords?|panels?|breakers?(?: box)?|fuse ?box(?:es)?|fuses?|meters?|fixtures?|"
    r"lights?|lamps?|bulbs?|fans?|motors?|wires?|wiring|chargers?|appliances?|"
    r"heaters?|walls?|ceilings?)\b"
)

# The parts that must never be hot to the touch (universe-electrical/docs/emergencies.md).
# Heaters, bulbs and light fittings get hot in normal use, so they are left out here.
_HOT_PARTS = (
    r"\b(?:outlets?|sockets?|receptacles?|(?:light |dimmer )?switch(?:es)?|switch plates?|"
    r"dimmers?|plugs?|cords?|panels?|breakers?(?: box)?|fuse ?box(?:es)?|fuses?|meters?|"
    r"wires?|wiring|chargers?)\b"
)

# The electrical trade (D-098). Gas and carbon monoxide are kept: any customer may report them.
# A breaker panel or a fuse box named on its own is not an emergency here, because an electrician
# is asked about panels every day; what makes one an emergency is a sign of heat, fire or shock.
ELECTRICAL_EMERGENCY_PATTERNS: dict[str, re.Pattern[str]] = {
    "gas_smell": EMERGENCY_PATTERNS["gas_smell"],
    "carbon_monoxide": EMERGENCY_PATTERNS["carbon_monoxide"],
    "burning_smell": re.compile(
        r"\b(?:burning|burnt|burned|melting|scorched?|singed|hot plastic)\b.{0,20}"
        r"\b(?:smell|smells|smelled|smelling|odou?r)\b"
        r"|\b(?:smell|smells|smelled|smelling|odou?r)\b.{0,25}"
        r"\b(?:burning|burnt|burned|melting|scorched?|hot plastic)\b"
        # a fishy smell is a classic sign of overheating, but only next to an electrical part
        r"|\bfishy\b.{0,20}\b(?:smell|smells|odou?r)\b.{0,30}"
        + _PARTS
        + r"|"
        + _PARTS
        + r".{0,30}\bfishy\b.{0,10}\b(?:smell|smells|odou?r)\b"
    ),
    "sparks_or_smoke": re.compile(
        r"\bspark(?:s|ed|ing|y)?\b|\barc(?:ing|ed)\b"
        # smoke near an electrical part; a smoke alarm or detector is not smoke
        r"|\bsmok(?:e|ed|es|ing)\b(?!\s*(?:alarm|detector)s?\b).{0,40}"
        + _PARTS
        + r"|"
        + _PARTS
        + r".{0,40}\bsmok(?:e|ed|es|ing)\b(?!\s*(?:alarm|detector)s?\b)"
        + r"|\b(?:on fire|caught fire|flames?)\b"
        # D-110: a part that crackles or sizzles, in the same clause, and a flash with a bang
        + r"|"
        + _PARTS
        + r"[^.!?;,]{0,30}\b(?:crackl|sizzl)\w*"
        + r"|\b(?:crackl|sizzl)\w*[^.!?;,]{0,30}"
        + _PARTS
        + r"|\b(?:blue|bright|white)\s+flash\b|\bflash\b.{0,15}\bpop\b|\bpop\b.{0,15}\bflash\b"
    ),
    "shock": re.compile(
        # "shocked at the price" is not a shock: a person must get one, or it must be electric
        r"\belectric(?:al)?\s+shocks?\b"
        r"|\b(?:got|get|gets|getting|gave me|giving|felt)\s+(?:a\s+)?(?:\w+\s+)?shocks?\b"
        r"|\bshocks?\s+(?:from|when|off)\b|\belectrocut\w*\b|\bgot a (?:jolt|zap)\b"
        r"|\b(?:got|get|gets|getting|was|were)\s+(?:\w+\s+)?(?:zapped|jolted)\b"
        r"|\b(?:felt|feel|feels|feeling)\s+(?:a\s+)?(?:\w+\s+)?tingl(?:e|es|ing)\b"
    ),
    "exposed_wires": re.compile(
        r"\b(?:exposed|bare|live|loose|dangling|hanging)\b.{0,10}\bwir(?:e|es|ing)\b"
        r"|\bwir(?:e|es|ing)\b.{0,25}\b(?:exposed|hanging|dangling|sticking out|poking out|"
        r"are live|is live|bare|visible|showing)\b"
        # D-110: wiring a person can see where a cover should be
        r"|\b(?:can|could)\s+see\b[^.!?;]{0,25}\bwir(?:e|es|ing)\b"
    ),
    "hot_fitting": re.compile(
        _HOT_PARTS + r".{0,45}"
        # "the breaker for the hot tub" is not a hot breaker, "warm white" is a colour
        r"\b(?:(?:is|are|feels?|felt|getting|gets|got|running|runs|too|very|really|so)\s+"
        r"(?:(?:really|very|too|so|quite|a bit)\s+)?(?:hot|warm)(?!\s+(?:tub|water|white|light|"
        r"glow|colou?r|tone))"
        r"|hot to the touch|warm to the touch|too hot to\b|melted|melting|scorched|blackened|"
        r"buzzing|scorch\w*|charred|heat damage|burn marks?|black marks?)\b"
        # D-110: the mark named first ("scorch marks on two breakers")
        r"|\b(?:scorch\w*|charred|heat damage|burn marks?|black marks?)\b[^.!?;]{0,30}" + _HOT_PARTS
    ),
    "downed_line": re.compile(
        r"\b(?:power|electric(?:al)?|utility|service)\s+(?:lines?|wires?|drop|cables?)\b.{0,40}"
        r"\b(?:down|fell|fallen|ground|snapped|lying|(?:pulled|ripped|torn) (?:down|off))\b"
        r"|\bdowned\s+(?:power\s+)?lines?\b"
        r"|\bwire\s+(?:to|into)\s+(?:our|the|my)\s+(?:house|home)\b.{0,40}"
        r"\b(?:down|off|fell|fallen|ground|snapped|lying)\b"
        # D-110: the wire from the pole, or a wire torn off the house
        r"|\b(?:wire|line|cable)s?\b.{0,25}\bfrom the pole\b.{0,60}"
        r"\b(?:down|off|fell|fallen|ground|snapped|lying|across)\b"
        r"|\b(?:brought down|pulled|ripped|tore|torn|knocked)\b.{0,15}\b(?:wire|line|cable)s?\b"
        r".{0,40}\b(?:pole|house|home)\b"
    ),
    "water_and_electrics": re.compile(
        r"\bwater\b(?!\s+(?:heater|softener|pump|filter|bill))"
        r".{0,60}\b(?:outlet|socket|panel|breaker|wiring|light fixture)s?\b"
        r"|\b(?:outlet|socket|panel|breaker|wiring)s?\b.{0,30}\b(?:wet|soaked|flooded)\b"
        # D-110: water coming out of or through a light
        r"|\bwater\b(?!\s+(?:heater|softener|pump|filter|bill|pressure|feature))[^.!?;]{0,30}"
        r"\b(?:through|into|out of|from|in)\s+(?:the\s+|a\s+|our\s+|my\s+)?(?:\w+\s+){0,2}"
        r"(?:lights?|fixtures?|light fittings?|lamps?)\b"
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


# A symptom the customer rules out ("no smell, no sparks, nothing hot", D-106). Only the word
# right before the symptom counts, in its own clause, and only for the electrical symptoms: the
# plumbing net is unchanged, and its "no water" is itself an emergency.
NEGATION = re.compile(r"\b(?:no|without|never)\s+$")
NEGATABLE = frozenset({"burning_smell", "sparks_or_smoke", "shock", "exposed_wires", "hot_fitting"})


def _is_negated(text: str, match: re.Match[str], breaks: list[tuple[int, int]]) -> bool:
    start = max((end for begin, end in breaks if end <= match.start()), default=0)
    return bool(NEGATION.search(text[start : match.start()]))


def _fires(
    name: str,
    pattern: re.Pattern[str],
    text: str,
    breaks: list[tuple[int, int]],
    imaginable: frozenset[str] = IMAGINABLE,
) -> bool:
    """True if any match of the pattern, overlapping ones included, is not past history, not
    (for water events) imagined, and not (for electrical symptoms) ruled out."""
    position = 0
    while (match := pattern.search(text, position)) is not None:
        if (
            not _is_history(text, match, breaks)
            and not (name in imaginable and _is_imagined(text, match, breaks))
            and not (name in NEGATABLE and _is_negated(text, match, breaks))
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
