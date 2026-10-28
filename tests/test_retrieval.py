"""Building the questions for the knowledge base and merging its answers (docs/TRD.md 4.4)."""

from typing import Any

import pytest

from citedesk.knowledge import FakeKB, KnowledgeBaseError
from citedesk.models import ExtractedFields, Intent, ServiceType
from citedesk.retrieval import (
    MAX_QUESTIONS,
    Question,
    build_questions,
    customer_questions,
    retrieve,
)

I = Intent  # noqa: E741


def fields(**over: Any) -> ExtractedFields:
    base: dict[str, Any] = {
        "service_type": None,
        "start_date": None,
        "property_type": None,
        "address_area": None,
        "preferred_contact": None,
        "booking_reference": None,
        "dates_as_written": None,
    }
    return ExtractedFields.model_validate(base | over)


def questions(
    *intents: Intent, body: str = "hello", subject: str | None = None, **field_over: Any
) -> list[Question]:
    return build_questions(
        intents=list(intents), fields=fields(**field_over), subject=subject, body=body
    )


# --- the customer's own questions ---------------------------------------------------------------


def test_question_sentences_are_taken_from_the_message() -> None:
    body = (
        "Hi there. My sink is slow. How much would a visit cost? And can you do Saturdays? Thanks"
    )
    assert customer_questions("", body) == "How much would a visit cost? And can you do Saturdays?"


def test_without_a_question_mark_the_subject_or_start_of_the_message_is_used() -> None:
    assert (
        customer_questions("Warranty on repairs", "Please tell me about it")
        == "Warranty on repairs"
    )
    assert customer_questions(None, "tell me about the warranty") == "tell me about the warranty"


def test_a_long_message_is_cut_short() -> None:
    assert len(customer_questions(None, "word " * 400)) <= 300


def test_at_most_two_question_sentences_are_used() -> None:
    assert customer_questions(None, "A? B? C? D?") == "A? B?"


# --- one question per thing the customer asks ----------------------------------------------------


def test_a_price_question_names_the_service() -> None:
    [q] = questions(I.pricing_question, service_type="water_heater")
    assert q.intent is I.pricing_question
    assert q.text == "How much does water heater service or replacement cost?"


def test_a_price_question_without_a_service_asks_about_prices_in_general() -> None:
    [q] = questions(I.pricing_question)
    assert q.text == "What are your prices and fees?"


def test_a_booking_asks_how_booking_works_for_that_service() -> None:
    [q] = questions(I.booking_request, service_type="drain_cleaning")
    assert "book drain cleaning" in q.text


def test_changing_and_cancelling_ask_about_the_policy() -> None:
    assert "reschedul" in questions(I.booking_change)[0].text.lower()
    assert "cancel" in questions(I.cancellation)[0].text.lower()


@pytest.mark.parametrize(
    "intent",
    [I.policy_question, I.service_question, I.billing_question, I.other],
)
def test_open_questions_carry_the_customers_own_words(intent: Intent) -> None:
    [q] = questions(intent, body="Do you give a warranty on repairs?")
    assert "Do you give a warranty on repairs?" in q.text


def test_the_service_gives_context_to_an_open_question() -> None:
    [q] = questions(I.policy_question, body="What is the warranty?", service_type="water_heater")
    assert q.text.startswith("About water heater service or replacement:")


@pytest.mark.parametrize(
    "intent",
    [I.availability_question, I.spam, I.health_or_safety, I.complaint, I.partnership_or_sales],
)
def test_some_intents_are_never_asked_of_the_knowledge_base(intent: Intent) -> None:
    assert questions(intent) == []


def test_each_intent_gets_its_own_question_primary_first() -> None:
    qs = questions(
        I.policy_question,
        I.pricing_question,
        I.availability_question,
        body="What is your warranty?",
        service_type="drain_cleaning",
    )
    assert [q.intent for q in qs] == [I.policy_question, I.pricing_question]


def test_identical_questions_are_asked_once_and_the_number_is_capped() -> None:
    qs = questions(
        I.cancellation,
        I.booking_change,
        I.policy_question,
        I.service_question,
        I.other,
        I.billing_question,
        body="Same words?",
    )
    assert len({q.text for q in qs}) == len(qs) and len(qs) <= MAX_QUESTIONS


def test_the_question_text_never_exceeds_the_knowledge_bases_limit() -> None:
    [q] = questions(I.other, body="x " * 3000 + "?")
    assert len(q.text) <= 2000


# --- asking and merging --------------------------------------------------------------------------


def q(text: str, intent: Intent = I.pricing_question) -> Question:
    return Question(intent=intent, text=text)


def test_each_answer_is_kept_with_its_question() -> None:
    kb = FakeKB(
        [
            FakeKB.answered("A costs $10.", ["pricing.md"]),
            FakeKB.answered("B is open.", ["hours.md"]),
        ]
    )
    got = retrieve(kb, [q("one"), q("two", I.service_question)])
    assert kb.questions == ["one", "two"]
    assert [r.question for r in got.results] == ["one", "two"]
    assert [r.result.answer for r in got.results] == ["A costs $10.", "B is open."]
    assert all(r.duration_ms >= 0 for r in got.results)
    assert got.unanswered == []


def test_sources_are_merged_without_repeats_in_order() -> None:
    first = FakeKB.answered("a", ["pricing.md", "faq.md"], text="same text")
    second = FakeKB.answered("b", ["pricing.md", "hours.md"], text="same text")
    got = retrieve(FakeKB([first, second]), [q("one"), q("two")])
    assert [(s.file, s.text) for s in got.sources] == [
        ("pricing.md", "same text"),
        ("faq.md", "same text"),
        ("hours.md", "same text"),
    ]


def test_a_declined_question_is_reported_not_answered() -> None:
    got = retrieve(
        FakeKB([FakeKB.answered("A.", ["a.md"]), FakeKB.declined()]),
        [q("one"), q("two", I.policy_question)],
    )
    assert got.unanswered == [I.policy_question]
    assert got.any_answered and not got.all_declined


def test_when_every_question_is_declined_nothing_is_grounded() -> None:
    got = retrieve(FakeKB([FakeKB.declined(), FakeKB.declined()]), [q("one"), q("two")])
    assert got.all_declined and not got.any_answered and got.sources == []


def test_no_questions_means_nothing_to_draft_from() -> None:
    kb = FakeKB([])
    got = retrieve(kb, [])
    assert got.all_declined and got.results == [] and kb.questions == []


def test_a_knowledge_base_error_is_not_swallowed() -> None:
    with pytest.raises(KnowledgeBaseError):
        retrieve(FakeKB([KnowledgeBaseError("unavailable", "down")]), [q("one")])


def test_the_service_label_covers_every_service_type() -> None:
    for service in ServiceType:
        assert questions(I.pricing_question, service_type=service.value)[0].text
