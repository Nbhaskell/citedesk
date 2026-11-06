"""Drafts must not ask for a detail the customer already gave (D-081): the draft step is told what
the earlier stages read, and the review aids mark a sentence that asks for one anyway."""

import sqlite3
from typing import Any

import pytest

from citedesk import drafting, pipeline, support
from citedesk.config import Settings
from citedesk.db import connect, migrate
from citedesk.models import ExtractedFields, Source
from citedesk.providers import FakeLLM
from tests.helpers import model_reply
from tests.test_pipeline_drafting import BUSINESS, GOOD_DRAFT, NOW, answering, retrieved

FIELDS = ExtractedFields(
    service_type="drain_cleaning",
    start_date=None,
    property_type="house",
    address_area="Wren Common",
    preferred_contact=None,
    booking_reference=None,
    dates_as_written=None,
)


# --- what is known ---------------------------------------------------------------------------


def test_known_details_are_the_fields_the_customer_gave_in_plain_words() -> None:
    assert drafting.known_details(FIELDS) == {
        "service_type": "drain cleaning",
        "property_type": "house",
        "address_area": "Wren Common",
    }


def test_unknown_and_empty_values_are_not_known() -> None:
    fields = FIELDS.model_copy(update={"service_type": "unknown", "address_area": " "})
    assert "service_type" not in drafting.known_details(fields)
    assert "address_area" not in drafting.known_details(fields)


def test_preferred_contact_and_dates_as_written_are_not_listed() -> None:
    fields = FIELDS.model_copy(update={"preferred_contact": "phone", "dates_as_written": "soon"})
    assert set(drafting.known_details(fields)) == {"service_type", "property_type", "address_area"}


# --- the draft step is told ------------------------------------------------------------------


def user_message(**over: Any) -> str:
    args: dict[str, Any] = {
        "first_name": "Alex",
        "subject": "Drain",
        "body": "My sink in Wren Common is slow.",
        "sources": [Source(file="a.md", section="s", page=None, text="Drain cleaning: $149")],
        "missing_fields": [],
        "unanswered": [],
        "sensitive_data_masked": False,
    }
    return drafting.build_user_message(**(args | over))


def test_the_user_message_lists_the_details_already_given_and_the_values() -> None:
    text = user_message(known={"address_area": "Wren Common", "property_type": "house"})
    assert "already gave" in text and "do not ask" in text.lower()
    assert "- area: Wren Common" in text and "- property type: house" in text


def test_nothing_is_added_when_nothing_is_known() -> None:
    assert "already gave" not in user_message(known={})
    assert "already gave" not in user_message()


def test_a_detail_that_is_also_missing_is_not_listed_as_known() -> None:
    text = user_message(known={"address_area": "Wren Common"}, missing_fields=["address_area"])
    assert "already gave" not in text


def test_the_system_prompt_says_never_to_ask_for_a_detail_already_given() -> None:
    prompt = " ".join(drafting.build_system_prompt(BUSINESS, 200).lower().split())
    assert drafting.PROMPT_VERSION == "draft-v4"
    assert "never ask for a detail the customer already gave" in prompt
    assert "even if a passage says it is needed" in prompt


# --- the pipeline passes what the extraction read -----------------------------------------------


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = connect(":memory:")
    migrate(c)
    return c


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)


def test_the_pipeline_tells_the_writer_the_area_the_customer_gave(
    conn: sqlite3.Connection, settings: Settings
) -> None:
    reply = model_reply(
        fields=model_reply()["fields"] | {"address_area": "Wren Common", "property_type": "house"}
    )
    inquiry_id = retrieved(
        conn, settings, answering(), reply, body="How much to clear a drain in Wren Common?"
    )
    llm = FakeLLM([GOOD_DRAFT])
    pipeline.draft_stage(conn, inquiry_id, settings, llm, BUSINESS, now=NOW)
    sent = llm.calls[0].user
    assert "already gave" in sent and "- area: Wren Common" in sent


def test_an_area_the_model_read_that_the_message_does_not_contain_is_not_passed_on(
    conn: sqlite3.Connection, settings: Settings
) -> None:
    reply = model_reply(
        fields=model_reply()["fields"] | {"address_area": "Kestrel Hollow Plumbing"}
    )
    inquiry_id = retrieved(conn, settings, answering(), reply)
    llm = FakeLLM([GOOD_DRAFT])
    pipeline.draft_stage(conn, inquiry_id, settings, llm, BUSINESS, now=NOW)
    assert (
        "Kestrel Hollow Plumbing"
        not in llm.calls[0].user.split("<sources>")[0].split("</inquiry>")[-1]
    )
    assert "- area:" not in llm.calls[0].user


# --- the review aids mark a question for something known -----------------------------------------

SRC = [
    Source(
        file="service-area.md",
        section="What we need to book a visit",
        page=None,
        text="Please tell us the type of work, the date, the property type and the neighbourhood.",
    )
]
KNOWN = {"address_area": "Wren Common", "property_type": "house"}


def marked(sentence: str, known: dict[str, str] | None = None) -> support.SentenceSupport:
    body = f"Hi Cecily,\n\n{sentence}\n\nKind regards,\nKestrel Hollow Plumbing"
    result = support.analyse(body, SRC, "My sink in Wren Common is slow.", known_fields=known)
    return result.sentences[0]


def test_a_request_for_the_area_is_marked_when_the_area_is_known() -> None:
    found = marked("Please provide the neighbourhood or address area.", KNOWN)
    assert found.status == "asks_known" and found.asks_for == ["area"]


def test_a_request_for_several_details_names_each_one_that_is_known() -> None:
    found = marked("Please confirm the property type and neighbourhood or address area.", KNOWN)
    assert found.status == "asks_known" and found.asks_for == ["area", "property type"]


def test_a_request_for_a_detail_that_is_not_known_is_left_alone() -> None:
    found = marked("Please let us know the date you would like us to visit.", KNOWN)
    assert found.status != "asks_known" and found.asks_for == []


def test_a_statement_that_mentions_the_area_is_not_a_request() -> None:
    found = marked("We do serve the neighbourhood of Wren Common.", KNOWN)
    assert found.status != "asks_known"


def test_nothing_is_marked_when_the_known_details_are_not_passed() -> None:
    assert marked("Please provide the neighbourhood or address area.").status != "asks_known"


# --- a detail the model read wrongly must not be handed back as known ----------------------------


def test_an_area_that_is_not_in_the_message_is_not_known() -> None:
    fields = FIELDS.model_copy(update={"address_area": "Millrace"})
    assert "address_area" not in drafting.known_details(fields, message="my sink in Wren Common")


def test_an_area_in_the_message_is_known_whatever_the_case() -> None:
    known = drafting.known_details(FIELDS, message="my sink in WREN COMMON is slow")
    assert known["address_area"] == "Wren Common"


def test_the_business_name_is_never_the_customers_area() -> None:
    fields = FIELDS.model_copy(update={"address_area": "Kestrel Hollow Plumbing"})
    known = drafting.known_details(
        fields,
        message="forwarded from Kestrel Hollow Plumbing",
        business_name="Kestrel Hollow Plumbing",
    )
    assert "address_area" not in known


def test_the_other_details_are_kept_when_only_the_area_fails_the_check() -> None:
    known = drafting.known_details(FIELDS, message="a slow sink", business_name="X")
    assert set(known) == {"service_type", "property_type"}
