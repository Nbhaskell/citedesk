"""What a reviewer is shown beside a draft: where each figure comes from, and which sentences no
source backs (D-077).

The trial in D-066 found that a person reading a draft that passed every check did not catch six
planted problems: an invented perk, a credit nobody offered, a wrong name, a price taken from
another service's line, a soft promise, a sentence about how the desk works. This module is plain
code and a warning only. It does not block, route or change a draft, and it does not decide that
anything is true: "supported" means a sentence uses the words and figures of one source passage,
nothing more. A sentence marked "unsupported" is one for a person to look at.

Everything it returns is text for the page to show as text (rule 5).
"""

import re
from typing import Literal

from pydantic import Field

from citedesk.checks import GREETING, MAX_GREETING_WORDS, SIGN_OFF, Figure, extract_figures
from citedesk.models import Source, Strict

Status = Literal["supported", "routine", "from_message", "unsupported", "tone"]

SUPPORT_OVERLAP = 0.6  # share of a sentence's content words that one source passage must hold
MESSAGE_OVERLAP = 0.75  # share that the customer's own message must hold
MISMATCH_OVERLAP = 0.5  # below this, a figure's line is about something else than the sentence
MAX_ORIGINS = 3

_WORD = re.compile(r"[a-z0-9']+")
_ENDINGS = ("ing", "ion", "ed", "ly")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=(?-i:[A-Z$\"'(]))")
_LIST_LINE = re.compile(r"^\s*[-*•]\s+")

# Words that carry no claim of their own: function words, and the words every pricing sentence
# uses ("starts", "costs", "fee"), which would otherwise make any price sentence look backed.
_STOP = frozenset(
    {
        "with", "that", "this", "have", "will", "your", "from", "they", "them", "also", "when",
        "what", "which", "would", "could", "should", "about", "around", "after", "before", "into",
        "there", "their", "been", "were", "than", "then", "just", "such", "some", "more", "most",
        "only", "very", "does", "doing", "each", "other", "here", "happy", "please", "thanks",
        "thank", "starts", "start", "starting", "costs", "cost", "price", "prices", "charge",
        "charges", "charged", "fees", "cover", "covers", "team", "member", "confirm", "details",
        "detail", "help", "need", "needs", "like", "know", "regards", "kind", "yes", "ask", "asked",
        "can", "any", "our", "are", "for", "the", "and",
    }
)  # fmt: skip

# Sentences that only manage the conversation and assert nothing about the business.
_ROUTINE = re.compile(
    r"^(?:thanks|thank you)\b[^.!?]{0,60}\b(?:message|enquiry|inquiry|getting in touch|reaching out"
    r"|contacting us|writing)\b"
    r"|\b(?:a member of our team|a team member|someone from our team|our team|we)(?: will|'ll) "
    r"(?:confirm|follow up|get back|reply|contact|check|look|be in touch|review|call|email)\b"
    r"|\b(?:feel free to|let us know|reply to this)\b"
    r"|\bif you have any (?:other |further |more )?questions\b"
    r"|^please (?:don't|do not) send card",
    re.IGNORECASE,
)


_SYMPATHY = re.compile(
    r"^(?:we(?:'re| are)? (?:sorry|glad|happy)\b|we understand\b|we appreciate\b|sorry\b)",
    re.IGNORECASE,
)
_PROMISE = re.compile(r"\b(?:refund|credit|discount|free|waive|guarantee|promise)", re.IGNORECASE)
MAX_SYMPATHY_WORDS = 14
# Sympathy the message may not call for (D-080). "Sorry to hear" answers a problem; "glad to hear"
# answers good news. A sentence is marked as tone when the sentiment the model read does not fit.
_SORRY = re.compile(
    r"^(?:we(?:'re| are)? (?:so )?sorry|sorry|we apologi[sz]e|apologies)\b", re.IGNORECASE
)
_GLAD = re.compile(
    r"^(?:we(?:'re| are)? (?:glad|happy|pleased|delighted) to hear|we appreciate"
    r"|we are grateful)\b",
    re.IGNORECASE,
)
_REFUSAL = re.compile(
    r"\b(?:but|unfortunately|unable|cannot|can't|don't|do not|not able)\b", re.IGNORECASE
)
UNHAPPY = frozenset({"negative", "angry"})


def _misplaced_sympathy(plain: str, sentiment: str | None) -> bool:
    """A sympathy sentence the message does not call for. Nothing is judged when the sentiment
    is unknown, and an apology that softens a refusal is always in place."""
    if sentiment is None:
        return False
    if _SORRY.match(plain):
        return sentiment not in UNHAPPY and not _REFUSAL.search(plain)
    if _GLAD.match(plain):
        return sentiment != "positive"
    return False


class Origin(Strict):
    source_index: int
    file: str
    section: str
    line: str
    context: str = Field(exclude=True, default="")  # the whole line, for the mismatch test


class FigureOrigin(Strict):
    figure: str
    sentence: str
    origins: list[Origin]
    from_message: bool
    mismatch: bool


class SentenceSupport(Strict):
    text: str
    status: Status
    source_index: int | None


class DraftSupport(Strict):
    greeting_name: str | None
    figures: list[FigureOrigin]
    sentences: list[SentenceSupport]


def _content(text: str) -> set[str]:
    words: set[str] = set()
    for raw in _WORD.findall(text.lower().replace("’", "'")):
        word = raw.strip("'")
        if len(word) < 4 or word.isdigit() or word in _STOP:
            continue
        if word.endswith("ies") and len(word) > 5:
            word = word[:-3] + "y"
        elif word.endswith("s") and not word.endswith("ss") and len(word) > 4:
            word = word[:-1]
        for ending in _ENDINGS:
            if word.endswith(ending) and len(word) - len(ending) >= 5:
                word = word[: -len(ending)]
                break
        words.add(word)
    return words


def _keys(figures: list[Figure]) -> set[tuple[str, object]]:
    return {(f.kind, f.key) for f in figures}


def _frame_free(body: str) -> tuple[str | None, list[str]]:
    """The greeting's name, and the lines between the greeting and the sign-off."""
    lines = [line.strip() for line in body.strip().splitlines() if line.strip()]
    name: str | None = None
    if lines and GREETING.match(lines[0]) and len(lines[0].split()) <= MAX_GREETING_WORDS:
        words = lines[0].rstrip(",.! ").split()
        name = words[-1] if len(words) > 1 else None
        lines = lines[1:]
    for index in range(max(0, len(lines) - 3), len(lines)):
        if SIGN_OFF.search(lines[index]) and len(lines[index].split()) <= MAX_GREETING_WORDS:
            lines = lines[:index]
            break
    return name, lines


def _sentences(lines: list[str]) -> list[str]:
    found: list[str] = []
    for line in lines:
        if _LIST_LINE.match(line):
            found.append(_LIST_LINE.sub("", line))
        else:
            found += [part.strip() for part in _SENTENCE_SPLIT.split(line) if part.strip()]
    return found


def _lines_of(source: Source) -> list[tuple[str, str]]:
    """Each sentence of the passage, with the whole bullet or paragraph it sits in."""
    pairs: list[tuple[str, str]] = []
    for raw in source.text.splitlines():
        whole = _LIST_LINE.sub("", raw.strip())
        if whole:
            pairs += [
                (part.strip(), whole) for part in _SENTENCE_SPLIT.split(whole) if part.strip()
            ]
    return pairs


def _origins(figure: Figure, sources: list[Source]) -> list[Origin]:
    found: list[Origin] = []
    for index, source in enumerate(sources):
        for line, whole in _lines_of(source):
            if (figure.kind, figure.key) in _keys(extract_figures(line)):
                found.append(
                    Origin(
                        source_index=index,
                        file=source.file,
                        section=source.section,
                        line=line,
                        context=whole,
                    )
                )
                break
    return found[:MAX_ORIGINS]


def _mismatch(figure: Figure, sentence_words: set[str], origins: list[Origin]) -> bool:
    """A price whose line is about something else than the sentence. Plain counts are not tested:
    "about 2 hours" sits in a line of its own words."""
    if figure.kind not in ("money", "percent") or not origins or not sentence_words:
        return False
    best = max(len(sentence_words & _content(o.context)) / len(sentence_words) for o in origins)
    return best < MISMATCH_OVERLAP


def analyse(
    body: str, sources: list[Source], inquiry_text: str, sentiment: str | None = None
) -> DraftSupport:
    """Judge each sentence of a draft against its sources and the customer's message, and find the
    line each figure comes from. Deterministic; changes nothing."""
    name, lines = _frame_free(body)
    message_words = _content(inquiry_text)
    message_keys = _keys(extract_figures(inquiry_text))
    source_words = [_content(s.text) for s in sources]
    source_keys = [_keys(extract_figures(s.text)) for s in sources]

    sentences: list[SentenceSupport] = []
    figures: list[FigureOrigin] = []
    seen: set[tuple[str, object]] = set()
    for sentence in _sentences(lines):
        found = extract_figures(sentence)
        keys = _keys(found)
        words = _content(sentence)

        wrong_line = False
        for figure in found:
            origins = _origins(figure, sources)
            mismatch = _mismatch(figure, words, origins)
            wrong_line = wrong_line or mismatch
            if (figure.kind, figure.key) in seen:
                continue
            seen.add((figure.kind, figure.key))
            figures.append(
                FigureOrigin(
                    figure=figure.shown.rstrip(",.;: "),
                    sentence=sentence,
                    origins=origins,
                    from_message=(figure.kind, figure.key) in message_keys,
                    mismatch=mismatch,
                )
            )

        plain = sentence.replace("’", "'")
        status: Status = "unsupported"
        source_index: int | None = None
        if (
            not found
            and _ROUTINE.search(plain)
            or (
                not found
                and _SYMPATHY.match(plain)
                and len(sentence.split()) <= MAX_SYMPATHY_WORDS
                and not _PROMISE.search(plain)
            )
        ):
            status = "tone" if _misplaced_sympathy(plain, sentiment) else "routine"
        elif not words and not found:
            status = "routine"  # nothing in it to assert
        else:
            scores = [(len(words & w) / len(words) if words else 0.0) for w in source_words]
            # The best passage that also holds every figure of the sentence. A passage with the
            # same words and no figure must not hide the one that has it.
            fitting = [
                i
                for i, score in enumerate(scores)
                if score >= SUPPORT_OVERLAP and keys <= (source_keys[i] | message_keys)
            ]
            if fitting and not wrong_line:
                status, source_index = "supported", max(fitting, key=scores.__getitem__)
            elif (
                words
                and len(words & message_words) / len(words) >= MESSAGE_OVERLAP
                and keys <= (message_keys)
            ):
                status = "from_message"
        sentences.append(SentenceSupport(text=sentence, status=status, source_index=source_index))
    return DraftSupport(greeting_name=name, figures=figures, sentences=sentences)
