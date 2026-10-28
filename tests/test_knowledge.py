import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from citedesk.knowledge import (
    FakeKB,
    KBResult,
    KnowledgeBase,
    KnowledgeBaseError,
    RagProjectKB,
    http_post_json,
    is_refusal,
)
from citedesk.models import Source

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def recorded(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / f"rag_ask_{name}.json").read_text("utf-8"))
    return data["response"]


class Post:
    def __init__(self, reply: dict[str, Any] | Exception) -> None:
        self.reply = reply
        self.calls: list[tuple[str, dict[str, Any], float]] = []

    def __call__(self, url: str, payload: dict[str, Any], timeout_s: float) -> dict[str, Any]:
        self.calls.append((url, payload, timeout_s))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def kb(reply: dict[str, Any] | Exception) -> tuple[RagProjectKB, Post]:
    post = Post(reply)
    return RagProjectKB("http://127.0.0.1:8000", post=post), post


# --- the refusal test --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "answer",
    [
        "I don't know.",
        "I do not know.",
        "I don’t know based on the documents.",
        "  i don't know",
        "I'm not sure. The documents do not say.",
        "The documents do not say whether we work on boats.",
        "The context does not mention a licence number.",
        "There is no information about that.",
        "I cannot find that in the documents.",
        "I can't answer that from the provided context.",
        "",
    ],
)
def test_these_answers_are_refusals(answer: str) -> None:
    assert is_refusal(answer)


@pytest.mark.parametrize(
    "answer",
    [
        "Drain cleaning starts at $149.",
        "No. We serve homes and small residential buildings only.",
        "Yes, we work on Saturdays. I don't know of any extra fee.",
        "The office is open on Tuesday afternoon. However, we cannot confirm a time.",
        "We do not do gas work. Call 911 from outside the building.",
    ],
)
def test_these_answers_are_not_refusals(answer: str) -> None:
    assert not is_refusal(answer)


def test_only_the_first_sentence_decides() -> None:
    assert not is_refusal("Standard visits are 2 to 4 days out. I don't know the exact day.")


# --- RagProjectKB ------------------------------------------------------------------------------


def test_the_request_is_the_question_trimmed_and_capped() -> None:
    adapter, post = kb(recorded("answered"))
    adapter.ask("  How much does drain cleaning cost?  ")
    [(url, payload, timeout_s)] = post.calls
    assert url == "http://127.0.0.1:8000/api/ask"
    assert payload == {"question": "How much does drain cleaning cost?"}
    assert timeout_s > 0
    adapter.ask("x" * 5000)
    assert len(post.calls[1][1]["question"]) == 2000


def test_history_is_sent_as_user_messages_when_given() -> None:
    adapter, post = kb(recorded("answered"))
    adapter.ask("And on weekends?", history=["How much is drain cleaning?"])
    assert post.calls[0][1]["history"] == [
        {"role": "user", "content": "How much is drain cleaning?"}
    ]


def test_a_recorded_answer_becomes_sources_the_reviewer_can_see() -> None:
    adapter, _ = kb(recorded("answered"))
    result = adapter.ask("How much does drain cleaning cost?")
    assert not result.declined and result.decline_reason is None
    assert result.answer.startswith("Drain cleaning for one fixture")
    assert {s.file for s in result.sources} == {"faq.md", "pricing.md"}
    assert result.sources[0].file == "faq.md"  # best match first, one entry per passage
    first = result.sources[0]
    assert isinstance(first, Source)
    assert first.section == "How much does drain cleaning cost?" and first.page is None
    assert "$149" in first.text
    assert result.raw["sources"] == ["faq.md", "pricing.md"]


def test_only_passages_the_answer_listed_are_kept() -> None:
    reply = recorded("answered")
    listed = [p for p in reply["passages"] if p["listed"]]
    assert 0 < len(listed) < len(reply["passages"]) or len(listed) == len(reply["passages"])
    result = kb(reply)[0].ask("q")
    assert len(result.sources) == len(listed)


def test_a_recorded_unrelated_question_is_a_decline_with_no_sources() -> None:
    result = kb(recorded("unrelated"))[0].ask("What will the weather be like tomorrow?")
    assert result.declined and result.decline_reason == "no_sources"
    assert result.sources == []


def test_sources_listed_but_a_refusal_in_the_first_sentence_is_still_a_decline() -> None:
    reply = recorded("answered") | {"answer": "I don't know. The documents mention up to 4 units."}
    result = kb(reply)[0].ask("Do you service air conditioners?")
    assert result.declined and result.decline_reason == "refusal"
    assert result.sources  # kept, so the reviewer can see what was found


def test_a_partial_answer_is_not_a_decline_here() -> None:
    # The recorded availability reply is why availability is handled in code (D-045).
    result = kb(recorded("partial_availability"))[0].ask("Anyone free next Tuesday?")
    assert not result.declined


@pytest.mark.parametrize(
    "reply",
    [
        {},
        {"answer": 3},
        {"answer": "x", "passages": "no"},
        {"answer": "x", "passages": [1]},
    ],
)
def test_a_reply_in_the_wrong_shape_is_an_error(reply: dict[str, Any]) -> None:
    with pytest.raises(KnowledgeBaseError) as caught:
        kb(reply)[0].ask("q")
    assert caught.value.reason == "bad_response"


def test_errors_from_the_call_pass_through() -> None:
    error = KnowledgeBaseError("unavailable", "could not connect to the knowledge base")
    with pytest.raises(KnowledgeBaseError) as caught:
        kb(error)[0].ask("q")
    assert caught.value.reason == "unavailable"


@pytest.mark.parametrize(
    "url", ["http://example.com:8000", "http://192.168.0.5:8000", "ftp://127.0.0.1", ""]
)
def test_only_this_machine_is_allowed(url: str) -> None:
    with pytest.raises(ValueError, match="loopback|http"):
        RagProjectKB(url, post=Post({}))


def test_it_is_a_knowledge_base() -> None:
    assert isinstance(kb({})[0], KnowledgeBase)


# --- the real HTTP call, simulated -------------------------------------------------------------


def test_http_errors_are_mapped_without_repeating_the_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private = "my private street name"

    def refuse(*a: Any, **k: Any) -> Any:
        raise urllib.error.URLError(ConnectionRefusedError(private))

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    with pytest.raises(KnowledgeBaseError) as caught:
        http_post_json("http://127.0.0.1:8000/api/ask", {"question": private}, 5)
    assert caught.value.reason == "unavailable" and private not in str(caught.value)

    def slow(*a: Any, **k: Any) -> Any:
        raise TimeoutError(private)

    monkeypatch.setattr(urllib.request, "urlopen", slow)
    with pytest.raises(KnowledgeBaseError) as caught:
        http_post_json("http://127.0.0.1:8000/api/ask", {"question": private}, 5)
    assert caught.value.reason == "timeout" and private not in str(caught.value)

    def busy(*a: Any, **k: Any) -> Any:
        raise urllib.error.HTTPError("u", 503, private, {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr(urllib.request, "urlopen", busy)
    with pytest.raises(KnowledgeBaseError) as caught:
        http_post_json("http://127.0.0.1:8000/api/ask", {"question": private}, 5)
    assert caught.value.reason == "bad_response" and "503" in str(caught.value)
    assert private not in str(caught.value)


# --- FakeKB ------------------------------------------------------------------------------------


def test_the_fake_replies_in_order_and_records_questions() -> None:
    first = KBResult(answer="a", declined=False, sources=[], raw={})
    fake = FakeKB([first, KnowledgeBaseError("unavailable", "down")])
    assert fake.ask("one") is first
    with pytest.raises(KnowledgeBaseError):
        fake.ask("two", history=["h"])
    assert fake.questions == ["one", "two"]
    with pytest.raises(AssertionError, match="more times"):
        fake.ask("three")


def test_the_fake_can_answer_from_the_question() -> None:
    fake = FakeKB(
        lambda q: FakeKB.answered("ok", ["pricing.md"]) if "cost" in q else FakeKB.declined()
    )
    assert not fake.ask("what does it cost").declined
    assert fake.ask("tell me a story").declined


def test_the_fake_helpers_build_realistic_results() -> None:
    result = FakeKB.answered("Starts at $149.", ["pricing.md"], text="Drain cleaning: $149")
    assert (
        result.sources[0].file == "pricing.md" and result.sources[0].text == "Drain cleaning: $149"
    )
    assert not result.declined
    refusal = FakeKB.declined()
    assert refusal.declined and refusal.sources == [] and refusal.decline_reason == "no_sources"
    assert isinstance(FakeKB(), KnowledgeBase)
