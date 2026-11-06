"""What a reviewer is shown beside a draft (D-077): where each figure comes from, and which
sentences no source backs. Plain code; warnings only. Invented text throughout."""

from citedesk import support
from citedesk.models import Source

DRAIN = Source(
    file="pricing.md",
    section="Pricing > Drain cleaning",
    page=None,
    text="- Drain cleaning, one fixture (sink, tub, shower or toilet): $149 (starting price)\n"
    "- Main sewer line cleaning: $329",
)
LEAK = Source(
    file="pricing.md",
    section="Pricing > Leak detection",
    page=None,
    text="- Leak detection (electronic, finds the source of a hidden leak): $245. Credited toward "
    "the repair if the customer approves it during the same visit.",
)
WARRANTY = Source(
    file="policies.md",
    section="Policies > Warranty",
    page=None,
    text="Repairs carry a 90-day workmanship warranty on labour. Parts carry the manufacturer's "
    "warranty.",
)
SOURCES = [DRAIN, LEAK, WARRANTY]
ASK = "How much to clear my slow kitchen sink in Wren Common?"


def frame(*paragraphs: str, name: str = "Cecily") -> str:
    return "\n\n".join([f"Hi {name},", *paragraphs, "Kind regards,\nKestrel Hollow Plumbing"])


def run(*paragraphs: str, inquiry: str = ASK, sources: list[Source] | None = None):
    return support.analyse(frame(*paragraphs), SOURCES if sources is None else sources, inquiry)


def statuses(result: support.DraftSupport) -> list[str]:
    return [s.status for s in result.sentences]


# --- sentences ---------------------------------------------------------------------------------


def test_a_sentence_that_restates_a_source_is_supported_and_names_it() -> None:
    result = run("Drain cleaning for one fixture starts at $149.")
    assert statuses(result) == ["supported"]
    assert result.sentences[0].source_index == 0


def test_a_paraphrase_of_a_source_is_still_supported() -> None:
    assert statuses(run("A single-fixture drain cleaning starts around $149.")) == ["supported"]


def test_an_invented_perk_is_not_supported() -> None:
    assert statuses(run("Platinum customers get priority scheduling forever.")) == ["unsupported"]


def test_an_unlisted_credit_is_not_supported() -> None:
    assert statuses(run("We will also credit $20 to your next visit.")) == ["unsupported"]


def test_a_description_of_how_the_desk_works_is_not_supported() -> None:
    result = run("Our replies are drafted by an assistant from a set of documents.")
    assert statuses(result) == ["unsupported"]


def test_a_promise_to_arrive_at_a_time_is_not_routine() -> None:
    assert statuses(run("A member of our team will be at your door first thing.")) == [
        "unsupported"
    ]


def test_a_price_from_the_wrong_service_is_not_supported() -> None:
    assert statuses(run("Leak detection costs $149.")) == ["unsupported"]


def test_boilerplate_that_asserts_nothing_is_routine() -> None:
    result = run(
        "Thanks for getting in touch.",
        "A member of our team will confirm the details.",
        "If you have any other questions, feel free to ask.",
    )
    assert statuses(result) == ["routine", "routine", "routine"]


def test_a_sentence_that_repeats_the_customers_own_message_is_marked_as_theirs() -> None:
    result = run("You asked about the slow kitchen sink in Wren Common.")
    assert statuses(result) == ["from_message"]


def test_the_greeting_and_the_sign_off_are_not_sentences() -> None:
    result = run("Drain cleaning for one fixture starts at $149.")
    assert len(result.sentences) == 1
    assert result.greeting_name == "Cecily"


def test_each_sentence_of_a_paragraph_is_judged_separately() -> None:
    result = run(
        "Drain cleaning for one fixture starts at $149. We also offer free lifetime pipes."
    )
    assert statuses(result) == ["supported", "unsupported"]


def test_a_decimal_does_not_split_a_sentence() -> None:
    result = run(
        "Sales tax is 7.5% on parts.",
        sources=[
            Source(
                file="pricing.md",
                section="Pricing > Tax",
                page=None,
                text="Parts carry sales tax. Sales tax on parts is 7.5%.",
            )
        ],
    )
    assert len(result.sentences) == 1


def test_a_draft_with_no_sources_has_no_supported_sentence() -> None:
    result = run("Drain cleaning for one fixture starts at $149.", sources=[])
    assert statuses(result) == ["unsupported"]


def test_an_empty_body_gives_an_empty_result() -> None:
    result = support.analyse("", SOURCES, ASK)
    assert result.sentences == [] and result.figures == [] and result.greeting_name is None


# --- figures -----------------------------------------------------------------------------------


def test_a_figure_is_shown_with_the_line_it_comes_from() -> None:
    figure = run("Drain cleaning for one fixture starts at $149.").figures[0]
    assert figure.figure == "$149" and not figure.mismatch
    origin = figure.origins[0]
    assert (origin.source_index, origin.file, origin.section) == (
        0,
        "pricing.md",
        "Pricing > Drain cleaning",
    )
    assert origin.line.startswith("Drain cleaning, one fixture") and "$149" in origin.line
    assert "$329" not in origin.line  # only the line, not the whole passage


def test_a_price_taken_from_another_services_line_is_marked_as_a_mismatch() -> None:
    figure = run("Hidden leak detection starts at $149.").figures[0]
    assert figure.origins[0].line.startswith("Drain cleaning")
    assert figure.mismatch is True


def test_a_figure_in_no_source_has_no_origin() -> None:
    figure = run("Hidden leak detection is $500.").figures[0]
    assert figure.origins == [] and figure.from_message is False


def test_a_figure_the_customer_gave_is_marked_as_theirs() -> None:
    figure = run(
        "With your $300 budget we can start with a visit.", inquiry="Budget is $300"
    ).figures[0]
    assert figure.from_message is True and figure.origins == []


def test_a_figure_found_in_two_sources_lists_both() -> None:
    other = Source(
        file="faq.md",
        section="FAQ > Drains",
        page=None,
        text="Drain cleaning for one fixture is $149 at the standard rate.",
    )
    figure = run("Drain cleaning starts at $149.", sources=[DRAIN, other]).figures[0]
    assert [o.source_index for o in figure.origins] == [0, 1]


def test_a_figure_is_listed_once_even_if_it_appears_twice() -> None:
    result = run("Drain cleaning starts at $149. Again, drain cleaning is $149.")
    assert [f.figure for f in result.figures] == ["$149"]


# --- properties --------------------------------------------------------------------------------


def test_the_result_is_the_same_every_time() -> None:
    body = frame("Drain cleaning for one fixture starts at $149. Free pipes for life.")
    assert support.analyse(body, SOURCES, ASK) == support.analyse(body, SOURCES, ASK)


def test_the_result_holds_only_text_the_page_shows_as_text() -> None:
    result = run("Drain cleaning starts at $149 <script>alert(1)</script>.")
    # Returned as plain strings for the page to render as text (rule 5); nothing is interpreted.
    assert all(isinstance(s.text, str) for s in result.sentences)


# --- found when the first version was run over real drafts (D-077) ----------------------------


def test_other_ways_to_say_a_person_will_follow_up_are_routine() -> None:
    result = run(
        "A team member will confirm the details once they visit.",
        "Our team will follow up to confirm the details.",
        "We'll be in touch shortly.",
    )
    assert statuses(result) == ["routine", "routine", "routine"]


def test_a_short_expression_of_sympathy_is_routine_but_not_when_it_carries_a_promise() -> None:
    assert statuses(run("We're sorry to hear about the charge on your invoice.")) == ["routine"]
    assert statuses(run("We're sorry, and we will refund the whole charge.")) == ["unsupported"]


def test_word_endings_do_not_hide_a_match() -> None:
    paid = Source(
        file="policies.md",
        section="Policies > Payment",
        page=None,
        text="Payment is due on completion of the work.",
    )
    assert statuses(run("Payment is due once the work is completed.", sources=[paid])) == [
        "supported"
    ]


def test_a_plain_count_is_never_called_a_mismatch() -> None:
    inspection = Source(
        file="pricing.md",
        section="Pricing > Inspections",
        page=None,
        text="- Whole-home plumbing inspection with written summary: $225. About 2 hours.",
    )
    result = run("The whole-home inspection takes about 2 hours.", sources=[inspection])
    assert all(not f.mismatch for f in result.figures)


def test_the_figure_is_shown_without_the_punctuation_that_followed_it() -> None:
    assert run("Our drain cleaning fee is $149, as listed.").figures[0].figure == "$149"


def test_a_price_is_judged_against_the_whole_line_it_sits_in_not_one_sentence_of_it() -> None:
    fee = Source(
        file="pricing.md",
        section="Pricing > Call-out fee",
        page=None,
        text="The standard call-out fee is $89. It covers travel and diagnosis, and it "
        "is credited toward the work if the customer approves it.",
    )
    result = run("The call-out fee is $89 and covers travel and diagnosis.", sources=[fee])
    assert not result.figures[0].mismatch


def test_a_curly_apostrophe_is_read_like_a_straight_one() -> None:
    assert statuses(run("We’re sorry to hear that.")) == ["routine"]


def test_a_passage_with_the_same_words_but_no_figure_does_not_hide_the_one_that_has_it() -> None:
    about = Source(
        file="services.md",
        section="Services > Inspections",
        page=None,
        text="A camera inspection of a drain or sewer line. Pricing: flat price.",
    )
    price = Source(
        file="pricing.md",
        section="Pricing > Inspections",
        page=None,
        text="- Camera inspection of a drain or sewer line: $175",
    )
    result = run("A camera inspection of a drain or sewer line is $175.", sources=[about, price])
    assert statuses(result) == ["supported"]
    assert result.sentences[0].source_index == 1


# --- sympathy the message does not call for (D-080) ---------------------------------------------

CANCEL = "Please cancel booking KH-4471. Sorry for the trouble, I got the part and did it myself."


def tone(*paragraphs: str, sentiment: str | None, inquiry: str = ASK) -> list[str]:
    result = support.analyse(frame(*paragraphs), SOURCES, inquiry, sentiment=sentiment)
    return statuses(result)


def test_sympathy_the_message_does_not_call_for_is_marked_as_tone() -> None:
    assert tone(
        "We're sorry to hear you managed to do the work yourself.", sentiment="neutral"
    ) == ["tone"]


def test_the_same_sentence_is_routine_when_the_customer_is_unhappy() -> None:
    sentence = "We're sorry to hear about the charge on your invoice."
    assert tone(sentence, sentiment="negative") == ["routine"]
    assert tone(sentence, sentiment="angry") == ["routine"]


def test_an_apology_that_softens_a_refusal_is_not_marked() -> None:
    assert "tone" not in tone("We're sorry, but we don't offer discounts.", sentiment="neutral")
    assert "tone" not in tone("Sorry, we cannot confirm that today.", sentiment="neutral")


def test_gladness_and_thanks_are_marked_unless_the_customer_is_pleased() -> None:
    glad = "We're glad to hear our technician was helpful."
    assert tone(glad, sentiment="neutral") == ["tone"]
    assert tone(glad, sentiment="positive") == ["routine"]
    assert tone("We appreciate your prompt payment.", sentiment="neutral") == ["tone"]


def test_with_no_sentiment_known_nothing_is_marked_as_tone() -> None:
    assert tone("We're sorry to hear that.", sentiment=None) == ["routine"]


def test_a_sympathy_sentence_that_promises_something_is_still_unsupported() -> None:
    assert tone("We're sorry, and we will refund the charge.", sentiment="neutral") == [
        "unsupported"
    ]


def test_an_ordinary_sentence_is_never_marked_as_tone() -> None:
    assert tone("Drain cleaning for one fixture starts at $149.", sentiment="neutral") == [
        "supported"
    ]


def test_a_short_sentence_sharing_one_word_with_the_message_is_not_taken_for_an_echo() -> None:
    """Found when claims were separated for the judge (D-082): one shared word is not a repeat."""
    result = run(
        "We can also help with any other plumbing needs you may have.",
        inquiry="Our plumbing is old and the sink is slow.",
    )
    assert statuses(result) == ["unsupported"]


def test_a_longer_echo_of_the_message_is_still_marked_as_theirs() -> None:
    result = run("You asked about the slow kitchen sink in Wren Common.")
    assert statuses(result) == ["from_message"]


# --- a price the documents hold and the draft does not give (under-answering) -------------------

HEATER = Source(
    file="pricing.md",
    section="Pricing > Water heaters",
    page=None,
    text="- Water heater replacement, 40-gallon tank, installed: $1,650\n"
    "- Water heater replacement, 50-gallon tank, installed: $1,850",
)
HEATER_ASK = "How much to replace my 50-gallon water heater tank?"


def unanswered(*paragraphs: str, inquiry: str = HEATER_ASK, sources: list[Source] | None = None):
    pool = [DRAIN, LEAK, WARRANTY, HEATER] if sources is None else sources
    return support.analyse(frame(*paragraphs), pool, inquiry).unanswered


def test_a_price_question_whose_price_is_in_the_documents_but_not_in_the_draft_is_marked() -> None:
    found = unanswered("A member of our team will confirm a quote for you.")
    assert found is not None
    assert found.kind == "price"
    assert found.origin.file == "pricing.md"
    assert found.origin.line.startswith("Water heater replacement, 50-gallon")
    assert found.origin.source_index == 3


def test_a_draft_that_gives_a_price_is_not_marked() -> None:
    assert unanswered("Replacing a 50-gallon water heater tank is $1,850.") is None


def test_a_draft_that_gives_any_price_is_not_marked_even_if_it_is_the_wrong_one() -> None:
    """Whether a figure is right is the figure check's job and the figure list's; this mark is
    only for a draft that gives none."""
    assert unanswered("Replacing a 40-gallon water heater tank is $1,650.") is None


def test_a_message_that_does_not_ask_about_cost_is_not_marked() -> None:
    assert (
        unanswered("A member of our team will confirm.", inquiry="Do you replace water heaters?")
        is None
    )


def test_no_mark_when_the_documents_hold_no_price_for_what_was_asked() -> None:
    assert (
        unanswered("A member of our team will confirm a quote for you.", sources=[WARRANTY]) is None
    )
    assert (
        unanswered(
            "A member of our team will confirm a quote.",
            inquiry="How much to repaint my garage door?",
        )
        is None
    )


def test_a_price_line_for_other_work_with_one_shared_word_is_not_enough() -> None:
    other = Source(
        file="pricing.md",
        section="Pricing > Inspections",
        page=None,
        text="- Camera inspection of a drain or sewer line: $175",
    )
    assert (
        unanswered(
            "We will confirm a quote.",
            inquiry="How much to replace my water heater and check the drain?",
            sources=[other],
        )
        is None
    )


def test_the_line_for_what_was_asked_is_chosen_over_a_line_for_something_else() -> None:
    found = unanswered("We will send a quote.", sources=[DRAIN, HEATER])
    assert found is not None
    assert found.origin.section == "Pricing > Water heaters"
    assert "50-gallon" in found.origin.line


def test_the_mark_is_only_for_a_draft_the_aids_were_asked_about() -> None:
    result = run("Drain cleaning for one fixture starts at $149.")
    assert result.unanswered is None


def test_how_much_notice_is_not_a_question_about_price() -> None:
    fee = Source(
        file="policies.md",
        section="Policies > Cancellation",
        page=None,
        text="- To cancel a visit with less notice than 24 hours, a fee of $45 applies.",
    )
    assert (
        unanswered(
            "A member of our team will confirm.",
            inquiry="How much notice do I need to give to cancel a visit?",
            sources=[fee],
        )
        is None
    )


def test_a_price_the_customer_already_quoted_is_not_a_price_left_out() -> None:
    inquiry = "Another plumber quoted me $149 to clear my drain. Will you match their price?"
    assert (
        unanswered("A member of our team will follow up.", inquiry=inquiry, sources=[DRAIN]) is None
    )
