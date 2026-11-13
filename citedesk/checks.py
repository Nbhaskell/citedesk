"""Draft checks: plain code between the model's draft and a person's review (docs/TRD.md 4.6).

The model writes; these decide whether a draft may be shown as ready. A failed *blocking* check
sends the draft to a person marked blocked (the pipeline stage does that); the warnings are
shown to the reviewer and block nothing. `ADDRESSES_ASK` is judge-based, off by default, and not
run until it has been calibrated.

None of this is a guarantee. The figure check compares values, not meaning: it cannot tell that
"$149" was attached to the wrong service. The commitment check is a list of phrases, so a promise
worded some other way gets through. Read the notes in D-046.
"""

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from citedesk.models import (
    CheckCode,
    Claim,
    DraftKind,
    Intent,
    ReasonCode,
    ServiceType,
    Source,
)
from citedesk.screening import injection_flags
from citedesk.textnorm import normalise

BLOCKING: frozenset[CheckCode] = frozenset(
    {CheckCode.FIGURES_GROUNDED, CheckCode.NO_COMMITMENT, CheckCode.NO_INJECTION_ECHO}
)
REASONS: dict[CheckCode, ReasonCode] = {
    CheckCode.FIGURES_GROUNDED: ReasonCode.UNVERIFIED_FIGURE,
    CheckCode.NO_COMMITMENT: ReasonCode.POLICY_EXCEPTION_REQUEST,
    CheckCode.NO_INJECTION_ECHO: ReasonCode.INJECTION_SUSPECTED,
}
ECHO_WINDOW = 40  # characters of the system prompt that may not appear in a draft


def reason_for(code: CheckCode) -> ReasonCode:
    """The escalation reason for a blocking check. A warning check has none (KeyError)."""
    return REASONS[code]


@dataclass(frozen=True)
class CheckInput:
    subject: str | None
    body: str
    claims: list[Claim]
    sources: list[Source]
    inquiry_text: str  # the customer's subject and message, as stored (masked)
    trusted_text: str  # the business's own contact details and name, from the fact sheet
    kind: DraftKind
    max_words: int
    system_prompt: str = ""

    @property
    def draft_text(self) -> str:
        return f"{self.subject or ''}\n{self.body}"

    @property
    def sources_text(self) -> str:
        return "\n".join(source.text for source in self.sources)


@dataclass(frozen=True)
class CheckOutcome:
    code: CheckCode
    blocking: bool
    passed: bool
    detail: dict[str, Any] = field(default_factory=dict)


# --- figures -----------------------------------------------------------------------------------

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}  # fmt: skip
_MONTH = (
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
    r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
NUMBER_WORDS = {
    "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}  # fmt: skip

ISO_DATE = re.compile(r"\b\d{4}-(\d{2})-(\d{2})\b")
MONTH_DAY = re.compile(rf"\b{_MONTH}\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b", re.IGNORECASE)
DAY_MONTH = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTH}\b", re.IGNORECASE)
MONEY = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)")
PHONE = re.compile(r"\b\d{3}[-.\s]\d{4}\b")
PERCENT = re.compile(r"\b(\d+(?:\.\d+)?)\s?%")
TIME = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s?([ap])\.?m\b|\b(noon|midnight)\b", re.IGNORECASE)
WEEKDAY = re.compile(
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?\b", re.IGNORECASE
)
NUMBER = re.compile(
    r"\b(?:\d+(?:,\d{3})*(?:\.\d+)?(?:st|nd|rd|th)?|" + "|".join(NUMBER_WORDS) + r")\b",
    re.IGNORECASE,
)
# Spelled-out money ("fifty dollars", "two hundred bucks"): a figure like any other (D-091).
_UNITS = {
    "zero": 0, "one": 1, "a": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}  # fmt: skip
_SCALES = {"hundred": 100, "thousand": 1000}
_NUMBER_WORD = "|".join(sorted([*_UNITS, *_SCALES], key=len, reverse=True))
SPELLED_MONEY = re.compile(
    rf"\b((?:(?:{_NUMBER_WORD})[\s-]+(?:and[\s-]+)?)*(?:{_NUMBER_WORD}))\s+(?:dollars?|bucks)\b",
    re.IGNORECASE,
)


def spelled_number(words: str) -> int | None:
    """ "one hundred forty-nine" -> 149. None when the words do not make a number."""
    total, current, seen = 0, 0, False
    for word in re.split(r"[\s-]+", words.lower().strip()):
        if word in ("", "and"):
            continue
        if word in _UNITS:
            current += _UNITS[word]
        elif word == "hundred":
            current = max(current, 1) * 100
        elif word == "thousand":
            total += max(current, 1) * 1000
            current = 0
        else:
            return None
        seen = True
    return total + current if seen else None


@dataclass(frozen=True)
class Figure:
    kind: str  # money, date, time, phone, percent, weekday, number
    key: Any  # a comparable form of the value
    shown: str  # as written


def _tidy(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def _decimal_key(digits: str) -> str:
    try:
        return format(Decimal(digits.replace(",", "")).normalize(), "f")
    except InvalidOperation:
        return digits


def extract_figures(text: str) -> list[Figure]:
    """Money, dates, times, phone numbers, percentages, weekdays and other numbers in the text.

    Each piece of text is claimed by the first kind that matches it, so "7:30 am" is a time and
    not also the numbers 7 and 30. Spelled-out numbers from two to twelve count ("one" does not:
    it is too often just a word).
    """
    work = _tidy(text)
    found: list[Figure] = []

    def take(pattern: re.Pattern[str], make: Any) -> None:
        nonlocal work
        for match in list(pattern.finditer(work)):
            figure = make(match)
            if figure is not None:
                found.append(figure)
        work = pattern.sub(lambda m: " " * len(m.group(0)), work)

    def month_day(match: re.Match[str]) -> Figure:
        return Figure(
            "date", (MONTHS[match.group(1)[:3].lower()], int(match.group(2))), match.group(0)
        )

    def day_month(match: re.Match[str]) -> Figure:
        return Figure(
            "date", (MONTHS[match.group(2)[:3].lower()], int(match.group(1))), match.group(0)
        )

    def time_of_day(match: re.Match[str]) -> Figure:
        if match.group(4):
            return Figure("time", 720 if match.group(4).lower() == "noon" else 0, match.group(0))
        hour, minute = int(match.group(1)) % 12, int(match.group(2) or 0)
        return Figure(
            "time",
            (hour + (12 if match.group(3).lower() == "p" else 0)) * 60 + minute,
            match.group(0),
        )

    def number(match: re.Match[str]) -> Figure:
        word = match.group(0).lower()
        if word in NUMBER_WORDS:
            return Figure("number", str(NUMBER_WORDS[word]), match.group(0))
        return Figure("number", _decimal_key(re.sub(r"(st|nd|rd|th)$", "", word)), match.group(0))

    take(ISO_DATE, lambda m: Figure("date", (int(m.group(1)), int(m.group(2))), m.group(0)))
    take(MONTH_DAY, month_day)
    take(DAY_MONTH, day_month)
    take(MONEY, lambda m: Figure("money", _decimal_key(m.group(1)), m.group(0)))

    def spelled_money(match: re.Match[str]) -> Figure | None:
        value = spelled_number(match.group(1))
        return None if value is None else Figure("money", str(value), match.group(0))

    take(SPELLED_MONEY, spelled_money)
    take(PHONE, lambda m: Figure("phone", re.sub(r"\D", "", m.group(0)), m.group(0)))
    take(PERCENT, lambda m: Figure("percent", _decimal_key(m.group(1)), m.group(0)))
    take(TIME, time_of_day)
    take(WEEKDAY, lambda m: Figure("weekday", m.group(1).lower(), m.group(0)))
    take(NUMBER, number)
    return found


def _numeric_values(figures: Iterable[Figure]) -> set[Decimal]:
    return {Decimal(f.key) for f in figures if f.kind in ("number", "money", "percent")}


def check_figures_grounded(data: CheckInput) -> CheckOutcome:
    """Every amount, number, date and time in the draft is in the sources, the business's own
    details, or the customer's message. A sum of two source prices is shown as derived."""
    known = extract_figures(f"{data.sources_text}\n{data.inquiry_text}\n{data.trusted_text}")
    known_keys = {(f.kind, f.key) for f in known}
    known_numbers = _numeric_values(known)
    money = sorted(_numeric_values(f for f in known if f.kind == "money"))
    sums = {a + b for a in money for b in money}

    grounded: list[str] = []
    derived: list[str] = []
    ungrounded: list[str] = []
    for figure in extract_figures(data.draft_text):
        if (
            (figure.kind, figure.key) in known_keys
            or figure.kind == "number"
            and Decimal(figure.key) in known_numbers
        ):
            bucket = grounded
        elif figure.kind == "money" and Decimal(figure.key) in sums:
            bucket = derived
        else:
            bucket = ungrounded
        if figure.shown not in bucket:
            bucket.append(figure.shown)
    return CheckOutcome(
        CheckCode.FIGURES_GROUNDED,
        True,
        not ungrounded,
        {"ungrounded": ungrounded, "derived": derived, "grounded": grounded},
    )


# --- commitments and advice ---------------------------------------------------------------------

# name -> (pattern, whether negation and "if/once" wording excuses it)
_PromiseSpec = tuple[re.Pattern[str], bool]


def _p(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


COMMITMENT_PATTERNS: Mapping[str, re.Pattern[str]] = {
    "booking confirmed": _p(
        r"\b(?:you(?:'re|’re| are)|we(?:'ve|’ve| have)|i(?:'ve|’ve| have))"
        r" (?:been )?(?:booked|scheduled)\b"
        r"|\b(?:booking|appointment|visit|slot|time|job) (?:is|has been|have been|are) "
        r"(?:all )?(?:confirmed|booked|scheduled|set|reserved)\b"
        r"|\b(?:confirmed|booked|scheduled) (?:for|on) (?:\w+day|\d)"
        r"|\bwe(?:'ll|’ll| will) (?:be there|arrive|see you)\b"
        r"|\bsee you (?:on|at|then|tomorrow)\b"
        # other wordings (D-091)
        r"|\blocked in\b|\bpencil+ed (?:you |it )?in\b"
        r"|\b(?:we )?(?:have|got) you (?:down|booked|scheduled|in) for\b"
        r"|\byou(?:'re|’re| are) all set\b"
        # someone will come, with a time: "a technician will come to check" names no time
        r"|\b(?:(?:a|an|our|the) (?:technician|plumber|electrician|tech|engineer) will "
        r"(?:be there|be with you|come|arrive|see you|be out"
        # "be at your door", the wording of a real draft (D-117)
        r"|be at your (?:door|home|house|place|property|address))"
        r"|we(?:'ll|’ll| will) send (?:a |an |our )?(?:technician|plumber|electrician|tech|engineer"
        r"|someone|somebody)(?: out| over| round)?)"
        r"(?: \w+){0,3} (?:on|at|by|tomorrow|today|tonight|this|next)\b"
    ),
    "refund promised": _p(
        r"\b(?:we|i|you)(?:'ll|’ll| will) (?:\w+ )?(?:refund|be refunded)\b"
        r"|\bfull refund\b|\bmoney back\b"
        r"|\b(?:issue|process|arrange)(?:d|ing)? (?:a |your |the )?refund\b"
        r"|\breimburs(?:e|ed|ing|ement)\b"
    ),
    "discount or waiver": _p(
        r"\b\d+\s?% (?:off|discount)\b|\bdiscount of\b"
        r"|\b(?:we|i)(?:'ll|’ll| will) (?:waive|discount|credit|comp)\b"
        r"|\bwaive[ds]? (?:the|your|that) (?:\w+ )?(?:fee|charge)\b"
        r"|\bat no (?:extra )?(?:charge|cost)\b|\bfree of charge\b|\bcomplimentary\b"
        r"|\bprice match\b"
        # other wordings (D-091)
        r"|\bhalf (?:price|off)\b|\b(?:percent|per cent) off\b"
        r"|\b(?:knock|take|shave)\w* (?:\S+ ){0,4}off (?:the|your)\b"
        r"|\b(?:apply|give|add|issue|put)\w* (?:\S+ ){0,3}(?:credit|rebate|discount)\b"
        r"|\b(?:take care of|cover|pick up) (?:the|your) (?:\w+ )?(?:fee|charge|cost|bill)\b"
        r"|\b(?:is|are|it's|it’s|be|was) (?:\w+ )?on (?:us|the house)\b"
    ),
    "guarantee": _p(r"\bguarantee[sd]?\b|\b(?:we|i) promise\b"),
}
# Promises worded as a negative ("you won't be charged"): a negation cannot excuse them, because
# the negation is the promise (D-091). Wording the sources use is still allowed.
NEGATIVE_PROMISE_PATTERNS: Mapping[str, re.Pattern[str]] = {
    "discount or waiver": _p(
        r"\b(?:won't|won’t|wont|will not|do not|don't|don’t|shouldn't|shouldn’t)"
        r" (?:have to |need to )?(?:be )?(?:pay|charged?)\b"
        r"|\bno charge\b|\bnot be charged\b|\bwithout charge\b"
    ),
}
ADVICE_PATTERNS: Mapping[str, re.Pattern[str]] = {
    "safety advice": _p(
        r"\b(?:turn off|shut off|switch off|leave the (?:building|house|home|property)"
        r"|evacuate|call 911|open (?:the )?windows|stop using|do not (?:use|touch|turn on)"
        r"|unplug)\b"
    ),
    "reassurance": _p(
        r"\b(?:is|are|it's|it is|it’s) (?:safe|not dangerous|harmless)\b"
        r"|\bno need to worry\b|\bdon't worry\b|\bdon’t worry\b"
        r"|\byou (?:should|will) be (?:fine|ok|okay)\b"
        # other wordings (D-091)
        r"|\bnothing to (?:worry|be (?:worried|concerned)) about\b"
        r"|\b(?:probably|likely|almost certainly|most likely) (?:nothing|fine|harmless|ok|okay"
        r"|not (?:serious|dangerous|a problem))\b"
        r"|\bnot (?:an emergency|serious|a concern|dangerous)\b"
        r"|\b(?:is|are|it's|it’s|it is) (?:perfectly |completely |totally |quite )?normal\b"
    ),
}
NEGATIONS = re.compile(
    r"\b(?:not|never|no|cannot|unable|without|nor|don't|doesn't|won't|can't|can’t"
    r"|don’t|doesn’t|won’t)\b|n't\b",
    re.IGNORECASE,
)
EXCUSES = re.compile(
    NEGATIONS.pattern + r"|\b(?:if|once|until|unless|when|after|pending|subject to)\b",
    re.IGNORECASE,
)
# A clause ends at a comma too: in "No problem, we'll refund you" the "no" belongs to the first
# clause and excuses nothing (D-091).
CLAUSE_START = re.compile(r"[.!?;:,\n]")
# Negative words that are only a figure of speech and deny nothing.
FIGURES_OF_SPEECH = re.compile(
    r"\b(?:no (?:problem|worries|worry|trouble)|not a problem|no need to worry)\b", re.IGNORECASE
)


def _clause_before(text: str, start: int) -> str:
    before = text[max(0, start - 60) : start]
    boundary = [m.end() for m in CLAUSE_START.finditer(before)]
    clause = before[boundary[-1] :] if boundary else before
    return FIGURES_OF_SPEECH.sub(" ", clause)


def _excused(text: str, start: int) -> bool:
    """Negation or "if/once/until" earlier in the same clause ("we cannot guarantee")."""
    return bool(EXCUSES.search(_clause_before(text, start)))


def _quotes_an_affirmative_source(phrase: str, sources: str) -> bool:
    """The phrase appears in the sources in a clause that does not deny it. "We do not offer a
    full refund" does not let a draft say "a full refund" (D-091)."""
    return any(
        not NEGATIONS.search(_clause_before(sources, m.start()))
        for m in re.finditer(re.escape(phrase), sources)
    )


def _subject_without_the_customers_words(data: CheckInput) -> str:
    """The reply subject minus the customer's own subject, which it usually repeats ("Re: price
    match?"). Repeating their words promises nothing; anything added still counts."""
    theirs = data.inquiry_text.split(chr(10), 1)[0].strip()
    subject = data.subject or ""
    if not theirs:
        return subject
    return re.sub(re.escape(theirs), " ", subject, flags=re.IGNORECASE)


SAME_ADVICE = re.compile(r"\b(?:shut(?:ting)? off|switch(?:ing)? off|turn(?:ing)? it off)\b")


def _canonical_advice(text: str) -> str:
    """Treat "shut off", "switch off" and "turn it off" as "turn off": the same advice."""
    return SAME_ADVICE.sub("turn off", text)


def check_no_commitment(
    data: CheckInput, *, patterns: Mapping[str, re.Pattern[str]] | None = None
) -> CheckOutcome:
    """No confirmed booking, refund, discount, guarantee, or advice the sources do not give.

    Wording that quotes the sources (the same words appear there) is allowed, and so is wording
    that denies or conditions the promise ("we cannot guarantee", "once it is confirmed").
    """
    text = normalise(f"{_subject_without_the_customers_words(data)} {data.body}")
    sources = _canonical_advice(normalise(data.sources_text))
    matched: list[str] = []
    promise_patterns = COMMITMENT_PATTERNS if patterns is None else patterns
    for name, pattern in promise_patterns.items():
        for hit in pattern.finditer(text):
            phrase = hit.group(0).lower()
            if _quotes_an_affirmative_source(phrase, sources) or _excused(text, hit.start()):
                continue
            if name not in matched:
                matched.append(name)
    if patterns is None:
        for name, pattern in NEGATIVE_PROMISE_PATTERNS.items():
            for hit in pattern.finditer(text):
                if hit.group(0).lower() not in sources and name not in matched:
                    matched.append(name)
        for name, pattern in ADVICE_PATTERNS.items():
            for hit in pattern.finditer(_canonical_advice(text)):
                if hit.group(0).lower() not in sources and name not in matched:
                    matched.append(name)
    return CheckOutcome(CheckCode.NO_COMMITMENT, True, not matched, {"matched_patterns": matched})


# --- structure ----------------------------------------------------------------------------------

MAX_GREETING_WORDS = 6
GREETING = re.compile(r"^(?:hi|hello|hey|dear|good (?:morning|afternoon|evening))\b", re.IGNORECASE)
SIGN_OFF = re.compile(
    r"\b(?:regards|best|sincerely|thanks|thank you|cheers|yours|take care)\b", re.IGNORECASE
)
JARGON_PHRASES = re.compile(
    r"\baccording to the (?:documents?|sources?|context|knowledge base)\b"
    r"|\bbased on the (?:provided |given )?(?:context|documents?|sources?|knowledge base)\b"
    r"|\bthe (?:provided |given )?(?:context|knowledge base)\b"
    r"|\bas an ai\b|\bsource \d+\b|\bpassage \d+\b",
    re.IGNORECASE,
)
INTERNAL_WORDS = frozenset(
    value.lower()
    for enum_class in (Intent, ReasonCode, CheckCode, DraftKind, ServiceType)
    for value in (member.value for member in enum_class)
    if "_" in value
)
SNAKE = re.compile(r"\b[a-z]+(?:_[a-z]+)+\b", re.IGNORECASE)


def check_structure(data: CheckInput) -> CheckOutcome:
    lines = [line.strip() for line in data.body.splitlines() if line.strip()]
    missing: list[str] = []
    # The greeting and the sign-off each stand on their own short line; a draft written as one
    # run-on paragraph with "Kind regards," in the middle of it is flagged (D-049).
    if not lines or not GREETING.match(lines[0]) or len(lines[0].split()) > MAX_GREETING_WORDS:
        missing.append("greeting")
    if not any(
        SIGN_OFF.search(line) and len(line.split()) <= MAX_GREETING_WORDS for line in lines[-3:]
    ):
        missing.append("sign_off")
    words = len(data.body.split())
    jargon = [m.group(0).lower() for m in JARGON_PHRASES.finditer(data.draft_text)]
    jargon += [
        m.group(0).lower()
        for m in SNAKE.finditer(data.draft_text)
        if m.group(0).lower() in INTERNAL_WORDS
    ]
    passed = not missing and words <= data.max_words and not jargon
    return CheckOutcome(
        CheckCode.STRUCTURE,
        False,
        passed,
        {"words": words, "max_words": data.max_words, "missing": missing, "jargon": jargon},
    )


# --- claims -------------------------------------------------------------------------------------


def check_claims_have_sources(data: CheckInput) -> CheckOutcome:
    bad = sorted({c.source_index for c in data.claims if c.source_index >= len(data.sources)})
    no_claims = data.kind is DraftKind.reply and not data.claims
    return CheckOutcome(
        CheckCode.CLAIMS_HAVE_SOURCES,
        False,
        not bad and not no_claims,
        {"bad_indices": bad, "no_claims": no_claims},
    )


# --- injection echo -----------------------------------------------------------------------------

LINK = re.compile(
    r"https?://[^\s<>\"')]+|www\.[^\s<>\"')]+|[\w.+-]+@[\w-]+(?:\.[\w-]+)+"
    # a bare domain ("kestrel-billing.net"), for the common endings only (D-091)
    r"|\b[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9-]+)*\.(?:com|net|org|info|biz|io|co|us"
    r"|app|online|site|xyz|shop|store|link|me|ly)\b(?:/[^\s<>\"')]*)?",
    re.IGNORECASE,
)


def _echoes_prompt(draft: str, prompt: str) -> bool:
    body, text = normalise(draft), normalise(prompt)
    return (
        any(
            text[i : i + ECHO_WINDOW] in body
            for i in range(0, max(1, len(text) - ECHO_WINDOW + 1), 5)
        )
        if len(text) >= ECHO_WINDOW
        else False
    )


def check_no_injection_echo(data: CheckInput) -> CheckOutcome:
    """The draft does not repeat the system prompt, contain instruction-injection wording, or
    point the customer at a link or address that is not in the sources or the business's own."""
    allowed = normalise(f"{data.sources_text}\n{data.trusted_text}")
    foreign = [
        link
        for link in dict.fromkeys(
            m.group(0).rstrip(".,;:!?") for m in LINK.finditer(data.draft_text)
        )
        if link.lower() not in allowed
    ]
    patterns = injection_flags(normalise(data.draft_text))
    echo = _echoes_prompt(data.draft_text, data.system_prompt)
    return CheckOutcome(
        CheckCode.NO_INJECTION_ECHO,
        True,
        not (foreign or patterns or echo),
        {
            "system_prompt_echo": echo,
            "injection_patterns": list(patterns),
            "foreign_links": foreign,
        },
    )


# --- all together -------------------------------------------------------------------------------


def run_checks(data: CheckInput) -> list[CheckOutcome]:
    """Every check, in a fixed order. This reports; the repository decides what a draft may be."""
    return [
        check_figures_grounded(data),
        check_no_commitment(data),
        check_claims_have_sources(data),
        check_structure(data),
        check_no_injection_echo(data),
    ]
