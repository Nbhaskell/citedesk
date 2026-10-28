"""Retrieval: the questions asked of the knowledge base, and what comes back (docs/TRD.md 4.4).

The questions are built in code, one per thing the customer asks, so what is sent to the knowledge
base is predictable. Some are fixed wording about a service ("How much does drain cleaning cost?");
the open ones (a policy, a service, a bill) carry the customer's own question sentences, cut short.

Live availability is never asked: it is not in the documents, and the knowledge base has answered
such questions with a partial answer that reads as helpful (D-045).
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from citedesk.knowledge import KBResult, KnowledgeBase, timed
from citedesk.models import ExtractedFields, Intent, Retrieval, ServiceType, Source

MAX_QUESTIONS = 3
MAX_CUSTOMER_TEXT = 300
MAX_QUESTION_SENTENCES = 2

SERVICE_LABELS: dict[ServiceType, str | None] = {
    ServiceType.emergency_repair: "emergency plumbing repair",
    ServiceType.drain_cleaning: "drain cleaning",
    ServiceType.leak_repair: "leak repair",
    ServiceType.sewer_line_repair: "sewer line repair",
    ServiceType.water_heater: "water heater service or replacement",
    ServiceType.fixture_installation: "fixture installation",
    ServiceType.inspection: "plumbing inspection",
    ServiceType.other: "plumbing repair",
    ServiceType.unknown: None,
}

# Never sent: nothing the documents say could answer them, or a person must see them first.
NOT_ASKED = frozenset(
    {
        Intent.availability_question,
        Intent.spam,
        Intent.health_or_safety,
        Intent.complaint,
        Intent.partnership_or_sales,
    }
)
OPEN_INTENTS = frozenset(
    {Intent.policy_question, Intent.service_question, Intent.billing_question, Intent.other}
)
BOOKING_INTENTS = frozenset({Intent.booking_request, Intent.booking_change, Intent.cancellation})

_SENTENCES = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Question:
    intent: Intent
    text: str


def _short(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut or text[:limit]


def customer_questions(subject: str | None, body: str) -> str:
    """The question sentences from the customer's message, or failing that its subject or start."""
    sentences = [s.strip() for s in _SENTENCES.split(" ".join(body.split())) if s.strip()]
    asked = [s for s in sentences if s.endswith("?")][:MAX_QUESTION_SENTENCES]
    if asked:
        return _short(" ".join(asked), MAX_CUSTOMER_TEXT)
    if subject and subject.strip():
        return _short(subject, MAX_CUSTOMER_TEXT)
    return _short(body, MAX_CUSTOMER_TEXT)


def _label(fields: ExtractedFields) -> str | None:
    return None if fields.service_type is None else SERVICE_LABELS[fields.service_type]


def _question_for(intent: Intent, fields: ExtractedFields, subject: str | None, body: str) -> str:
    label = _label(fields)
    if intent is Intent.pricing_question:
        return f"How much does {label} cost?" if label else "What are your prices and fees?"
    if intent is Intent.booking_request:
        return f"What is needed to book {label or 'plumbing work'} and how does booking work?"
    if intent is Intent.booking_change:
        return "How do I change or reschedule a booking, and what is the policy?"
    if intent is Intent.cancellation:
        return "What is the cancellation policy?"
    text = customer_questions(subject, body)
    return f"About {label}: {text}" if label else text


def build_questions(
    *,
    intents: Sequence[Intent],
    fields: ExtractedFields,
    subject: str | None,
    body: str,
    only_open: bool = False,
) -> list[Question]:
    """One question per askable intent, in the order given, without repeats.

    With `only_open`, the process questions (booking, changing, cancelling) are left out: a reply
    that asks for missing details already covers them.
    """
    found: list[Question] = []
    for intent in intents:
        if intent in NOT_ASKED or (only_open and intent in BOOKING_INTENTS):
            continue
        text = _short(_question_for(intent, fields, subject, body), 2000)
        if all(existing.text != text for existing in found):
            found.append(Question(intent=intent, text=text))
    return found[:MAX_QUESTIONS]


@dataclass(frozen=True)
class Answer:
    intent: Intent
    question: str
    result: KBResult
    duration_ms: int


@dataclass(frozen=True)
class Retrieved:
    results: list[Answer]

    @property
    def answered(self) -> list[Answer]:
        return [a for a in self.results if not a.result.declined]

    @property
    def any_answered(self) -> bool:
        return bool(self.answered)

    @property
    def all_declined(self) -> bool:
        """True when there is nothing grounded to draft from, including when nothing was asked."""
        return not self.any_answered

    @property
    def unanswered(self) -> list[Intent]:
        return [a.intent for a in self.results if a.result.declined]

    @property
    def sources(self) -> list[Source]:
        """Passages from the answered questions, merged in order without repeats."""
        merged: list[Source] = []
        for answer in self.answered:
            for source in answer.result.sources:
                if source not in merged:
                    merged.append(source)
        return merged


def retrieve(kb: KnowledgeBase, questions: Sequence[Question]) -> Retrieved:
    """Ask each question in turn. A knowledge-base error is not caught here."""
    results: list[Answer] = []
    for question in questions:
        result, elapsed_ms = timed(kb, question.text)
        results.append(Answer(question.intent, question.text, result, elapsed_ms))
    return Retrieved(results)


def merged_sources(rows: Sequence[Retrieval]) -> list[Source]:
    """The passages of the answered questions stored in the database, merged in order without
    repeats. This is the list the draft was written from, so a claim's `source_index` points into
    it; the check stage rebuilds it the same way."""
    merged: list[Source] = []
    for row in rows:
        if row.declined:
            continue
        for source in row.sources:
            if source not in merged:
                merged.append(source)
    return merged
