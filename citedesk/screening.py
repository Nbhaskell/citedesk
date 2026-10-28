"""Screening: the checks that run in code before any model reads a message.

Three detectors, all pure functions with no model and no network:

- sensitive data: card numbers (grouped like a card and passing the Luhn check) and US Social
  Security numbers are masked, keeping the last four digits;
- prompt injection: instruction-like text addressed to an assistant;
- spam: a weighted score from simple signals.

`screen` combines them. Results hold pattern names and kinds, never the matched text.
"""

import base64
import binascii
import re
from dataclasses import dataclass

from citedesk.models import ScreeningResult
from citedesk.safety import emergency_hits
from citedesk.textnorm import ZERO_WIDTH, normalise

# --- sensitive data --------------------------------------------------------------------------

CARD = re.compile(
    r"(?<!\d)(?:\d{13,19}|\d{4}(?:[ -]\d{4}){2,3}(?:[ -]\d{1,3})?|\d{4}[ -]\d{6}[ -]\d{5})(?!\d)"
)
SSN_FORMATTED = re.compile(r"(?<![\d-])(\d{3})[- ](\d{2})[- ](\d{4})(?![\d-])")
SSN_KEYWORD = re.compile(
    r"\b(?:ssn|social security(?: number)?|social sec(?:urity)?)\b[^0-9\n]{0,15}(\d{9})(?!\d)",
    re.IGNORECASE,
)
KIND_ORDER = ("card", "ssn")


def luhn_valid(number: str) -> bool:
    digits = [int(c) for c in number if c.isdigit()]
    if len(digits) != len(number) or not digits:
        return False
    total = 0
    for index, digit in enumerate(reversed(digits)):
        if index % 2 == 1:
            digit = digit * 2 - 9 if digit > 4 else digit * 2
        total += digit
    return total % 10 == 0


def _ssn_valid(area: str, group: str, serial: str) -> bool:
    return (
        area not in ("000", "666")
        and not area.startswith("9")
        and group != "00"
        and serial != "0000"
    )


def _mask_card(digits: str) -> str:
    masked = "*" * (len(digits) - 4) + digits[-4:]
    groups: list[str] = []
    end = len(masked)
    while end > 0:
        groups.insert(0, masked[max(0, end - 4) : end])
        end -= 4
    return " ".join(groups)


@dataclass(frozen=True)
class MaskResult:
    text: str
    kinds: list[str]


def mask_sensitive(text: str) -> MaskResult:
    """Mask card and Social Security numbers, keeping the last four digits."""
    spans: list[tuple[int, int, str, str]] = []
    for match in CARD.finditer(text):
        digits = re.sub(r"\D", "", match.group(0))
        if 13 <= len(digits) <= 19 and len(set(digits)) > 1 and luhn_valid(digits):
            spans.append((match.start(), match.end(), "card", _mask_card(digits)))
    for match in SSN_FORMATTED.finditer(text):
        if _ssn_valid(*match.groups()):
            spans.append((match.start(), match.end(), "ssn", f"***-**-{match.group(3)}"))
    for match in SSN_KEYWORD.finditer(text):
        digits = match.group(1)
        if _ssn_valid(digits[:3], digits[3:5], digits[5:]):
            spans.append((match.start(1), match.end(1), "ssn", f"***-**-{digits[5:]}"))

    kept: list[tuple[int, int, str, str]] = []
    for span in sorted(spans, key=lambda s: (s[0], -(s[1] - s[0]))):
        if not kept or span[0] >= kept[-1][1]:
            kept.append(span)
    result = text
    for start, end, _kind, replacement in reversed(kept):
        result = result[:start] + replacement + result[end:]
    found = {kind for _s, _e, kind, _r in kept}
    return MaskResult(result, [k for k in KIND_ORDER if k in found])


# --- prompt injection ------------------------------------------------------------------------

STRONG: dict[str, re.Pattern[str]] = {
    "ignore_previous": re.compile(
        r"\b(?:ignore|disregard|forget|override)\b\W+(?:(?:all|any|your|the|these|those)\W+)*"
        r"(?:previous|prior|above|earlier|preceding|original|system)\W+"
        r"(?:instructions?|prompts?|rules?|directions?|guidelines?|commands?)"
    ),
    "reveal_prompt": re.compile(
        r"\bsystem prompts?\b"
        r"|\b(?:print|reveal|repeat|output|display|leak|show)\b.{0,30}\byour\b.{0,25}"
        r"\b(?:instructions|rules|prompt)\b.{0,40}"
        r"\b(?:word for word|verbatim|you were given|you were told)\b"
    ),
    "persona_swap": re.compile(
        r"\byou are (?:now )?(?:(?:the )?owner'?s? (?:assistant|ai)\b|my assistant with|"
        r"an? (?:unrestricted|unfiltered|jailbroken)\b|"
        r"dan\b.{0,40}\b(?:assistant|ai|no rules|without))"
        r"|\bfrom now on\b.{0,30}\byou (?:are|will be)\b.{0,50}"
        r"\b(?:no rules|no restrictions|without (?:any )?(?:rules|restrictions|limits)|"
        r"unrestricted)\b"
        r"|\b(?:developer|jailbreak) mode\b"
    ),
    "hide_from_staff": re.compile(
        r"\b(?:do not|don't|dont|never)\b\W+(?:flag|tell|inform|notify|alert|report|mention)\b"
        r".{0,30}\b(?:staff|owner|team|reviewer|humans?|anyone)\b"
    ),
    "decode_and_follow": re.compile(
        r"\bdecode\b.{0,40}\b(?:and|then)\b.{0,15}\b(?:do|follow|execute|obey|run|act)\b"
    ),
}

WEAK: dict[str, re.Pattern[str]] = {
    "claims_authority": re.compile(
        r"\b(?:i am|i'm|this is)\b[^.!?]{0,40}\b(?:the owner|an? admin(?:istrator)?|"
        r"the administrator|the developer|"
        r"from (?:the )?(?:it|support|management) (?:team|department))\b"
    ),
    "authorises_you": re.compile(r"\bi (?:hereby )?authori[sz]e you to\b"),
    "reply_json": re.compile(r"\{\s*[\"“”']?(?:reply|response|answer|message)[\"“”']?\s*:"),
    "format_reply": re.compile(
        r"\bformat your (?:reply|response|answer) as\b"
        r"|\b(?:reply|respond|answer) (?:with|as|in) (?:only )?(?:json|xml|yaml)\b"
    ),
    "force_confirm": re.compile(
        r"\b(?:reply|respond|say|answer)\b.{0,10}\b(?:that|with)\b.{0,60}"
        r"\b(?:confirmed|approved|no charge|free of charge|full refund)\b"
    ),
}

BLOB = re.compile(r"[A-Za-z0-9+/]{24,}={0,2}")


def _decoded_text(blob: str) -> str | None:
    """The text inside a base64 blob, or None if it is not valid base64 holding mostly text."""
    padded = blob + "=" * (-len(blob) % 4)
    try:
        raw = base64.b64decode(padded, validate=True)
    except (binascii.Error, ValueError):
        return None
    if not raw:
        return None
    printable = sum(1 for b in raw if 32 <= b < 127 or b in (9, 10, 13))
    if printable / len(raw) < 0.9:
        return None
    return raw.decode("ascii", errors="ignore")


def _strong_hits(normalised: str) -> list[str]:
    return [name for name, pattern in STRONG.items() if pattern.search(normalised)]


def _weak_hits(normalised: str) -> list[str]:
    return [name for name, pattern in WEAK.items() if pattern.search(normalised)]


def injection_flags(text: str) -> list[str]:
    """Names of injection patterns found. Any strong pattern flags a message; weak patterns
    count only when two different ones appear together."""
    normalised = normalise(text)
    strong = _strong_hits(normalised)
    weak = _weak_hits(normalised)

    for blob in BLOB.findall(ZERO_WIDTH.sub("", text)):
        decoded = _decoded_text(blob)
        if decoded is None:
            continue
        inner = normalise(decoded)
        if _strong_hits(inner) or len(_weak_hits(inner)) >= 2:
            strong.append("encoded_instruction")
        else:
            weak.append("long_encoded_blob")

    if strong:
        return strong + (weak if len(set(weak)) >= 2 else [])
    return weak if len(set(weak)) >= 2 else []


# --- spam ------------------------------------------------------------------------------------

SPAM_PHRASES = (
    "click here",
    "guaranteed",
    "limited time",
    "limited spots",
    "act now",
    "unsubscribe",
    "winner",
    "congratulations",
    "you have been selected",
    "gift card",
    "claim your",
    "claim now",
    "no prescription",
    "buy meds",
    "lowest prices",
    "fast shipping",
    "crypto",
    "trading bot",
    "first page of google",
    "special price",
    "risk free",
    "risk-free",
    "100% free",
    "work from home",
    "earn money",
    "double your",
    "wire transfer",
    "account suspension",
    "action required",
    "will be closed",
)
URL = re.compile(r"https?://\S+|www\.\S+")
MONEY_HYPE = re.compile(r"\$\s?\d[\d,]{2,}\b.{0,30}\b(?:day|week|month|yesterday|daily)\b")
PHISH_TOPIC = re.compile(r"\b(?:invoice|statement|payment|account)\b")
PHISH_THREAT = re.compile(r"\b(?:overdue|suspend|suspension|closed|immediately|urgent|expire)")
# Plumbing and service vocabulary only. Words such as price, cost, quote or book also appear in
# spam, so they would hide the "no business words" signal.
BUSINESS = re.compile(
    r"plumb|drain|leak|toilet|water|pipe|sink|faucet|\btap\b|heater|sewer|shower|\btub\b|bath|"
    r"clog|flood|\bgas\b|\bhot\b|overflow|repair|install|appointment|warranty|invoice|receipt|"
    r"emergency"
)


SPAM_SIGNALS = (
    "phrases",
    "links",
    "link_only",
    "exclamations",
    "caps",
    "money_hype",
    "phishing_combo",
    "no_business_words",
)
# Flags that do not come from a named pattern in STRONG or WEAK.
DERIVED_FLAGS = ("encoded_instruction", "long_encoded_blob")


@dataclass(frozen=True)
class SpamResult:
    score: float
    signals: list[str]


def spam_score(subject: str, body: str) -> SpamResult:
    """A score from 0 to 1 built from simple signals. Capital letters alone can never reach the
    usual threshold, so an urgent message written in capitals is not mistaken for spam."""
    raw = f"{subject}\n{body}"
    text = normalise(raw)
    signals: list[str] = []
    score = 0.0

    phrases = sum(1 for phrase in SPAM_PHRASES if phrase in text)
    if phrases:
        signals.append("phrases")
        score += min(0.6, 0.25 * phrases)

    links = URL.findall(text)
    if links:
        signals.append("links")
        score += {1: 0.1, 2: 0.3}.get(len(links), 0.5)
        body_text = normalise(body)
        if body_text and sum(len(link) for link in URL.findall(body_text)) / len(body_text) >= 0.6:
            signals.append("link_only")
            score += 0.4

    if re.search(r"!{3,}", raw):
        signals.append("exclamations")
        score += 0.15

    letters = [c for c in raw if c.isalpha()]
    if len(letters) >= 40 and sum(c.isupper() for c in letters) / len(letters) >= 0.7:
        signals.append("caps")
        score += 0.1

    if MONEY_HYPE.search(text):
        signals.append("money_hype")
        score += 0.25

    if links and PHISH_TOPIC.search(text) and PHISH_THREAT.search(text):
        signals.append("phishing_combo")
        score += 0.3

    if not BUSINESS.search(text):
        signals.append("no_business_words")
        score += 0.2

    return SpamResult(round(min(1.0, score), 3), signals)


# --- the whole step --------------------------------------------------------------------------


@dataclass(frozen=True)
class ScreeningOutcome:
    subject: str | None
    body: str
    spam_score: float
    spam_signals: list[str]
    injection_flags: list[str]
    sensitive_kinds: list[str]
    emergency_hits: list[str]
    result: ScreeningResult


def screen(subject: str | None, body: str, *, spam_threshold: float) -> ScreeningOutcome:
    """Mask sensitive data, then look for injection, emergencies and spam in what remains.

    Injection beats spam. An emergency term stops a message being archived as spam. Nothing
    here reads the message with a model.
    """
    masked_body = mask_sensitive(body)
    masked_subject = mask_sensitive(subject) if subject is not None else None
    kinds = {*masked_body.kinds, *(masked_subject.kinds if masked_subject else [])}
    subject_text = masked_subject.text if masked_subject else None
    combined = f"{subject_text or ''}\n{masked_body.text}"

    spam = spam_score(subject_text or "", masked_body.text)
    flags = injection_flags(combined)
    emergencies = emergency_hits(combined)

    if flags:
        result = ScreeningResult.injection_suspected
    elif spam.score >= spam_threshold and not emergencies:
        result = ScreeningResult.spam
    else:
        result = ScreeningResult.clean
    return ScreeningOutcome(
        subject=subject_text,
        body=masked_body.text,
        spam_score=spam.score,
        spam_signals=spam.signals,
        injection_flags=flags,
        sensitive_kinds=[k for k in KIND_ORDER if k in kinds],
        emergency_hits=emergencies,
        result=result,
    )
