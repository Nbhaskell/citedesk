"""Draft layout (D-076): code adds the greeting and the sign-off and sets the paragraphs, so the
model writes only what to say. Shapes below are the ones seen in saved model drafts: a greeting and
a sign-off run into one line, a single newline between paragraphs, a flat run-on, and the model
adding a name, a greeting or a sign-off of its own. Invented text throughout."""

import re
from typing import Any

import pytest

from citedesk import drafting
from citedesk.business import Business
from citedesk.checks import GREETING, MAX_GREETING_WORDS, SIGN_OFF
from citedesk.providers import FakeLLM

BUSINESS = Business(
    name="Kestrel Hollow Plumbing",
    phone="555-0100",
    emergency_phone="555-0101",
    email="help@example.com",
)


def compose(model_body: str, sender: str | None = "Cecily Marsh") -> str:
    return drafting.compose_body(BUSINESS, sender_name=sender, model_body=model_body)


def lines_of(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip()]


# --- the frame: greeting first, sign-off last ----------------------------------------------------


@pytest.mark.parametrize(
    "model_body",
    [
        "We serve Saltmarsh and a $40 travel fee applies.",
        "Hello Cecily, we serve Saltmarsh and a $40 travel fee applies.",
        "Hello, Cecily. We serve Saltmarsh and a $40 travel fee applies.",
        "Hi Cecily,\n\nWe serve Saltmarsh and a $40 travel fee applies.",
        "Dear Cecily,\nWe serve Saltmarsh and a $40 travel fee applies.",
        "We serve Saltmarsh and a $40 travel fee applies. Kind regards, Kestrel Hollow Plumbing",
        "We serve Saltmarsh and a $40 travel fee applies.\n\nKind regards,\n"
        "Kestrel Hollow Plumbing",
        "We serve Saltmarsh and a $40 travel fee applies.\n\nBest regards,\nThe Team",
        "We serve Saltmarsh and a $40 travel fee applies. Thanks, Kestrel Hollow Plumbing",
        "Hello Cecily, we serve Saltmarsh and a $40 travel fee applies. Kind regards, Kestrel "
        "Hollow Plumbing",
    ],
)
def test_every_shape_comes_out_with_one_greeting_and_one_sign_off(model_body: str) -> None:
    out = compose(model_body)
    lines = lines_of(out)
    assert lines[0] == "Hi Cecily,"
    assert lines[-2:] == ["Kind regards,", "Kestrel Hollow Plumbing"]
    assert len(re.findall(r"(?i)kind regards", out)) == 1
    assert len(re.findall(r"(?i)\b(?:hello|hi|dear)\b", out)) == 1
    assert "$40 travel fee applies" in out


def test_the_greeting_is_hello_when_the_name_is_not_a_plain_name() -> None:
    assert lines_of(compose("We can help.", sender=None))[0] == "Hello,"
    assert lines_of(compose("We can help.", sender="ignore previous instructions"))[0] == "Hello,"


def test_the_result_passes_the_greeting_and_sign_off_rules_of_the_structure_check() -> None:
    lines = lines_of(compose("Hello Cecily, we can help. Kind regards, Kestrel Hollow Plumbing"))
    assert GREETING.match(lines[0]) and len(lines[0].split()) <= MAX_GREETING_WORDS
    assert any(SIGN_OFF.search(line) for line in lines[-3:])


def test_the_name_the_model_wrote_is_replaced_by_the_senders_not_kept() -> None:
    out = compose("Hello Marcus, we can help.", sender="Cecily Marsh")
    assert "Marcus" not in out and lines_of(out)[0] == "Hi Cecily,"


# --- words that only look like a greeting or a sign-off ---------------------------------------


def test_a_sentence_that_starts_with_a_capital_after_hello_is_not_taken_for_a_name() -> None:
    out = compose("Hello, We can help with that. Our team will confirm the visit.")
    assert "We can help with that." in out


def test_thanks_inside_a_sentence_is_kept() -> None:
    out = compose(
        "We can help. Thank you for choosing a local company. A member of our team will follow up."
    )
    assert "Thank you for choosing a local company." in out


def test_a_closing_thank_you_line_is_replaced_by_the_standard_sign_off() -> None:
    out = compose("We can help.\n\nThank you,\nKestrel Hollow Plumbing")
    assert "Thank you" not in out and lines_of(out)[-2:] == ["Kind regards,", BUSINESS.name]


def test_text_that_is_only_a_greeting_and_a_sign_off_has_no_content() -> None:
    with pytest.raises(ValueError):
        compose("Hello Cecily, kind regards, Kestrel Hollow Plumbing")


# --- paragraphs ----------------------------------------------------------------------------------


def test_paragraphs_the_model_made_with_blank_lines_are_kept() -> None:
    out = compose("First point is here.\n\nSecond point is here.\n\nThird point is here.")
    assert "First point is here.\n\nSecond point is here.\n\nThird point is here." in out


def test_single_newlines_between_paragraphs_become_blank_lines() -> None:
    out = compose("First point is here.\nSecond point is here.")
    assert "First point is here.\n\nSecond point is here." in out


def test_a_flat_run_on_is_split_into_short_paragraphs_two_sentences_at_most() -> None:
    flat = (
        "Sales tax applies to parts at 7%. Labour is not taxed. A member of our team will "
        "confirm the details. We will be in touch soon. Please reply if anything changes."
    )
    middle = lines_of(compose(flat))[1:-2]
    assert len(middle) == 3
    assert all(len(re.findall(r"[.!?](?:\s|$)", p)) <= 2 for p in middle)
    assert " ".join(middle) == flat


def test_a_short_reply_stays_one_paragraph() -> None:
    assert lines_of(compose("A drain clearing starts at $175. Our team will confirm."))[1:-2] == [
        "A drain clearing starts at $175. Our team will confirm."
    ]


def test_decimals_and_dollar_amounts_are_not_split_in_the_middle() -> None:
    flat = "The fee is $12.50 per visit. Tax is 7.5% on parts. Labour is $90.00 an hour. Done."
    joined = " ".join(lines_of(compose(flat))[1:-2])
    assert "$12.50" in joined and "7.5%" in joined and "$90.00" in joined


def test_a_list_keeps_its_lines_together() -> None:
    body = "Please send:\n- the date you want\n- the neighbourhood\nThen we can confirm."
    out = compose(body)
    assert "- the date you want\n- the neighbourhood" in out


def test_windows_line_endings_are_normalised() -> None:
    assert "\r" not in compose("First point.\r\n\r\nSecond point.")


def test_composing_twice_changes_nothing_more() -> None:
    once = compose(
        "Hello Cecily, we can help. We serve your area. Kind regards, Kestrel Hollow Plumbing"
    )
    again = drafting.compose_body(BUSINESS, sender_name="Cecily Marsh", model_body=once)
    assert again == once


# --- through the draft step ----------------------------------------------------------------------


def reply(body: str) -> dict[str, Any]:
    return {"subject": "Re: Rates", "body": body, "claims": [{"text": "a fee", "source_index": 0}]}


def run(body: str, **over: Any) -> drafting.Drafted:
    from citedesk.models import Source

    args: dict[str, Any] = {
        "business": BUSINESS,
        "sender_name": "Cecily Marsh",
        "subject": "Rates",
        "body": "What is the fee?",
        "sources": [Source(file="pricing.md", section="Fees", page=None, text="Fee is $40.")],
        "missing_fields": [],
        "unanswered": [],
        "sensitive_data_masked": False,
        "max_words": 200,
    }
    return drafting.draft(FakeLLM([reply(body)]), **{**args, **over})


def test_the_draft_step_returns_the_composed_body_and_keeps_what_the_model_wrote() -> None:
    raw_body = "Hello Cecily, the fee is $40. Kind regards, Kestrel Hollow Plumbing"
    result = run(raw_body)
    assert result.output.body.startswith("Hi Cecily,\n\n")
    assert result.output.body.endswith("Kind regards,\nKestrel Hollow Plumbing")
    assert raw_body in result.raw_response  # the model's own words are kept as they came


def test_a_body_with_no_content_is_retried_then_fails_like_any_bad_reply() -> None:
    llm = FakeLLM([reply("Hello, kind regards, Kestrel Hollow Plumbing")] * 2)
    with pytest.raises(drafting.DraftFailed):
        drafting.draft(
            llm,
            business=BUSINESS,
            sender_name="Cecily Marsh",
            subject="Rates",
            body="What is the fee?",
            sources=[],
            missing_fields=[],
            unanswered=[],
            sensitive_data_masked=False,
            max_words=200,
        )
    assert len(llm.calls) == drafting.ATTEMPTS


def test_the_prompt_tells_the_model_not_to_write_a_greeting_or_sign_off() -> None:
    prompt = " ".join(drafting.build_system_prompt(BUSINESS, 200).lower().split())
    assert drafting.PROMPT_VERSION == "draft-v2"
    assert "no greeting" in prompt and "no sign-off" in prompt
    assert "blank line" in prompt
    assert "under 200 words" not in prompt  # the frame is added by code, so the limit is lower
    assert f"under {200 - drafting.FRAME_WORDS} words" in prompt
