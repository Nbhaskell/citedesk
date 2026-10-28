import json
from typing import Any

import pytest

from citedesk.providers import (
    FakeLLM,
    LLMBadResponse,
    LLMCall,
    LLMError,
    LLMProvider,
    LLMTimeout,
    LLMUnavailable,
)

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}}


def ask(llm: LLMProvider, user: str = "hello", **over: Any) -> str:
    return llm.generate_json(system="be brief", user=user, schema=SCHEMA, **over).text


# --- FakeLLM ---------------------------------------------------------------------------------


def test_replies_come_back_in_order_as_json_text() -> None:
    llm = FakeLLM([{"ok": True}, [1, 2], '{"raw": "string"}'])
    assert json.loads(ask(llm)) == {"ok": True}
    assert json.loads(ask(llm)) == [1, 2]
    assert ask(llm) == '{"raw": "string"}'


def test_a_string_reply_is_sent_unchanged_so_tests_can_send_invalid_json() -> None:
    assert ask(FakeLLM(["not json {"])) == "not json {"


def test_a_scripted_exception_is_raised() -> None:
    llm = FakeLLM([LLMTimeout("too slow"), {"ok": True}])
    with pytest.raises(LLMTimeout):
        ask(llm)
    assert json.loads(ask(llm)) == {"ok": True}


def test_running_out_of_replies_is_a_test_bug_and_says_so() -> None:
    llm = FakeLLM([{"ok": True}])
    ask(llm)
    with pytest.raises(AssertionError, match="more times than it has replies"):
        ask(llm)


def test_a_function_can_choose_the_reply_from_the_call() -> None:
    def reply(call: LLMCall) -> dict[str, bool]:
        return {"ok": "yes" in call.user}

    llm = FakeLLM(reply)
    assert json.loads(ask(llm, "yes please")) == {"ok": True}
    assert json.loads(ask(llm, "no thanks")) == {"ok": False}


def test_every_call_is_recorded_with_its_settings() -> None:
    llm = FakeLLM([{"ok": True}])
    ask(llm, "question", temperature=0.2, max_tokens=50, timeout_s=9, seed=7, think=True)
    [call] = llm.calls
    assert call == LLMCall(
        system="be brief",
        user="question",
        schema=SCHEMA,
        temperature=0.2,
        max_tokens=50,
        timeout_s=9,
        seed=7,
        think=True,
    )


def test_defaults_match_the_trd() -> None:
    llm = FakeLLM([{"ok": True}])
    ask(llm)
    call = llm.calls[0]
    assert (call.temperature, call.max_tokens, call.timeout_s, call.seed, call.think) == (
        0.0,
        1500,
        120,
        0,
        False,
    )


def test_the_result_names_the_model() -> None:
    result = FakeLLM([{"ok": True}], model="tiny").generate_json(
        system="s", user="u", schema=SCHEMA
    )
    assert result.model == "tiny" and result.duration_ms >= 0 and not result.truncated


def test_the_fake_is_an_llm_provider() -> None:
    assert isinstance(FakeLLM(), LLMProvider)


def test_the_error_types_share_a_base() -> None:
    for error in (LLMUnavailable, LLMTimeout, LLMBadResponse):
        assert issubclass(error, LLMError)
