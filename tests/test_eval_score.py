"""The Phase 7 scorer, tested on hand-made runs whose right answers are known.

What the real system scores is the scorer's output, not something asserted here.
"""

from typing import Any

import pytest

from tools import eval_score as es

# --- builders ----------------------------------------------------------------------------------


def item(item_id: str, category: str = "routine_answerable", **label_over: Any) -> dict[str, Any]:
    labels: dict[str, Any] = {
        "intents": ["pricing_question"],
        "primary_intent": "pricing_question",
        "urgency": "normal",
        "fields": {
            "service_type": "drain_cleaning",
            "start_date": None,
            "property_type": None,
            "address_area": None,
        },
        "should_escalate": False,
        "expected_reason_codes": [],
        "expected_route": "draft_reply",
        "answerable_from_docs": True,
    }
    return {"id": item_id, "split": "tuned", "category": category, "labels": labels | label_over}


def escalate(*reasons: str, **over: Any) -> dict[str, Any]:
    return {
        "should_escalate": True,
        "expected_route": "escalate",
        "expected_reason_codes": list(reasons),
    } | over


def reason(code: str, source: str = "rule") -> dict[str, str]:
    return {"code": code, "source": source}


def check(code: str, passed: bool = True, blocking: bool = False, **detail: Any) -> dict[str, Any]:
    return {"code": code, "blocking": blocking, "passed": passed, "detail": detail}


ALL_PASS = [
    check("FIGURES_GROUNDED", blocking=True, ungrounded=[]),
    check("NO_COMMITMENT", blocking=True),
    check("CLAIMS_HAVE_SOURCES"),
    check("STRUCTURE"),
    check("NO_INJECTION_ECHO", blocking=True),
]


def record(item_id: str, **over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": item_id,
        "status": "needs_review",
        "route": "draft_reply",
        "urgency": "normal",
        "primary_intent": "pricing_question",
        "classified": True,
        "reasons": [],
        "failure_stage": None,
        "failure_message": None,
        "intents": [{"intent": "pricing_question", "confidence": "high"}],
        "primary_confidence": "high",
        "sentiment": "neutral",
        "model_urgency": "normal",
        "model_signals": [],
        "safety_net_hit": False,
        "fields": {
            "service_type": "drain_cleaning",
            "start_date": None,
            "property_type": "unknown",
            "address_area": None,
            "booking_reference": None,
        },
        "missing_fields": [],
        "model_ms": 1000,
        "attempts": 1,
        "stage_ms": {"screen": 1, "understand": 1000, "route": 1, "retrieve": 500, "draft": 3000},
        "route_events": [{"stage": "route", "route": "draft_reply", "reason_codes": []}],
        "retrievals": [],
        "draft": {"kind": "reply", "status": "ready", "model": "qwen3:8b"},
        "checks": ALL_PASS,
    }
    return base | over


def escalated(item_id: str, *reasons: dict[str, str], **over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "status": "escalated",
        "route": "escalate",
        "reasons": list(reasons),
        "route_events": [{"stage": "route", "route": "escalate", "reason_codes": []}],
        "draft": None,
        "checks": [],
    }
    return record(item_id, **(base | over))


def run_of(*records: dict[str, Any]) -> dict[str, Any]:
    return {"header": {"run_id": "r", "split": "tuned"}, "items": list(records)}


# --- what the labels imply for the whole pipeline ----------------------------------------------


def test_the_whole_pipeline_expects_the_labelled_route_and_every_labelled_reason() -> None:
    labels = item("x", **escalate("NOT_IN_KNOWLEDGE_BASE"))["labels"]
    assert es.expected_full(labels) == ("escalate", ["NOT_IN_KNOWLEDGE_BASE"])


def test_an_injection_item_expects_only_what_screening_can_see() -> None:
    labels = item("x", **escalate("INJECTION_SUSPECTED", "REFUND_OR_DISPUTE"))["labels"]
    assert es.expected_full(labels) == ("escalate", ["INJECTION_SUSPECTED"])
    gas = item("x", **escalate("INJECTION_SUSPECTED", "HEALTH_SAFETY"))["labels"]
    assert es.expected_full(gas)[1] == ["INJECTION_SUSPECTED", "HEALTH_SAFETY"]


# --- the five headline measures ----------------------------------------------------------------


def test_item_measures_give_each_item_a_numerator_and_a_denominator() -> None:
    golden = [
        item("ok"),
        item("wrong-intent"),
        item("safety", "safety", **escalate("HEALTH_SAFETY"), primary_intent="health_or_safety"),
        item("missed", **escalate("COMPLAINT"), primary_intent="complaint"),
        item("false-alarm"),
    ]
    run = run_of(
        record("ok"),
        record("wrong-intent", primary_intent="booking_request"),
        escalated(
            "safety", reason("HEALTH_SAFETY", "safety_net"), primary_intent="health_or_safety"
        ),
        record("missed", primary_intent="complaint"),
        escalated("false-alarm", reason("COMPLAINT")),
    )
    m = es.item_measures(run, golden)
    assert m["primary_intent"]["ok"] == (1.0, 1.0)
    assert m["primary_intent"]["wrong-intent"] == (0.0, 1.0)
    assert m["route"]["ok"] == (1.0, 1.0) and m["route"]["missed"] == (0.0, 1.0)
    assert m["escalation_recall"]["safety"] == (1.0, 1.0)
    assert m["escalation_recall"]["missed"] == (0.0, 1.0)
    assert m["escalation_recall"]["ok"] == (0.0, 0.0)  # nothing to catch
    assert m["escalation_precision"]["false-alarm"] == (0.0, 1.0)
    assert m["escalation_precision"]["safety"] == (1.0, 1.0)
    assert m["health_safety_recall"]["safety"] == (1.0, 1.0)
    assert m["health_safety_recall"]["ok"] == (0.0, 0.0)


def test_an_item_the_model_never_read_has_no_intent_score() -> None:
    golden = [item("spam", "spam", expected_route="archive", primary_intent="spam")]
    run = run_of(record("spam", status="archived", route="archive", classified=False))
    assert es.item_measures(run, golden)["primary_intent"]["spam"] == (0.0, 0.0)


def test_a_failed_item_counts_as_a_miss_on_route_and_recall() -> None:
    golden = [item("a", **escalate("HEALTH_SAFETY"))]
    run = run_of(record("a", status="failed", route=None, classified=False, reasons=[]))
    m = es.item_measures(run, golden)
    assert m["route"]["a"] == (0.0, 1.0)
    assert m["health_safety_recall"]["a"] == (0.0, 1.0)


def test_a_safety_reason_for_the_wrong_cause_is_not_enough_for_a_safety_item() -> None:
    golden = [item("a", **escalate("HEALTH_SAFETY"))]
    run = run_of(escalated("a", reason("COMPLAINT")))
    assert es.item_measures(run, golden)["health_safety_recall"]["a"] == (0.0, 1.0)


def test_the_headline_carries_counts_beside_every_rate() -> None:
    golden = [
        item("a"),
        item("b", **escalate("HEALTH_SAFETY"), primary_intent="health_or_safety"),
        item("c", **escalate("COMPLAINT"), primary_intent="complaint"),
        item("d"),
    ]
    run = run_of(
        record("a"),
        escalated("b", reason("HEALTH_SAFETY"), primary_intent="health_or_safety"),
        record("c", primary_intent="complaint"),
        escalated("d", reason("COMPLAINT"), primary_intent="booking_request"),
    )
    h = es.score_run(run, golden)["headline"]
    accuracy = h["primary_intent_accuracy"]
    assert (accuracy["numerator"], accuracy["denominator"], accuracy["value"]) == (3, 4, 0.75)
    assert accuracy["target"] == 0.85
    assert (h["route_accuracy"]["numerator"], h["route_accuracy"]["denominator"]) == (2, 4)
    assert (h["escalation_precision"]["numerator"], h["escalation_precision"]["denominator"]) == (
        1,
        2,
    )
    assert (h["escalation_recall"]["numerator"], h["escalation_recall"]["denominator"]) == (1, 2)
    assert h["health_safety_recall"]["value"] == 1.0
    assert h["health_safety_recall"]["denominator"] == 1
    assert h["health_safety_recall"]["missed"] == []


def test_a_missed_safety_item_is_named_in_the_headline() -> None:
    golden = [item("gas", "safety", **escalate("HEALTH_SAFETY"))]
    run = run_of(record("gas"))
    h = es.score_run(run, golden)["headline"]["health_safety_recall"]
    assert h["value"] == 0.0 and h["missed"] == ["gas"] and h["target_met"] is False


def test_the_safety_target_is_met_only_with_no_misses_and_at_least_one_item() -> None:
    golden = [item("gas", "safety", **escalate("HEALTH_SAFETY"))]
    run = run_of(escalated("gas", reason("HEALTH_SAFETY")))
    assert es.score_run(run, golden)["headline"]["health_safety_recall"]["target_met"] is True
    none = es.score_run(run_of(record("a")), [item("a")])["headline"]["health_safety_recall"]
    assert none["value"] is None and none["target_met"] is None


# --- escalation by reason, with the reasons only later stages can give -------------------------


def test_the_knowledge_base_reason_is_scored_like_the_others() -> None:
    golden = [item("a", **escalate("NOT_IN_KNOWLEDGE_BASE")), item("b")]
    run = run_of(
        escalated("a", reason("NOT_IN_KNOWLEDGE_BASE")),
        escalated("b", reason("NOT_IN_KNOWLEDGE_BASE")),
    )
    r = es.score_run(run, golden)["escalation"]["per_reason"]["NOT_IN_KNOWLEDGE_BASE"]
    assert (r["tp"], r["fp"], r["fn"]) == (1, 1, 0) and r["extra"] == ["b"]


def test_an_escalation_by_a_check_is_attributed_to_the_check() -> None:
    golden = [item("a")]
    run = run_of(
        escalated(
            "a",
            reason("POLICY_EXCEPTION_REQUEST", "check"),
            draft={"kind": "reply", "status": "blocked", "model": "qwen3:8b"},
        )
    )
    scores = es.score_run(run, golden)
    assert scores["escalation"]["by_source"] == {"check": 1}
    assert scores["escalation"]["escalated_by_a_check"] == ["a"]
    assert scores["escalation"]["false_positives"] == ["a"]


# --- stages 1 to 3, comparable with the first baseline -----------------------------------------


def test_stage_three_is_scored_apart_from_the_whole_pipeline() -> None:
    """Routed to a draft, then escalated because the knowledge base had nothing."""
    golden = [item("a", **escalate("NOT_IN_KNOWLEDGE_BASE"))]
    run = run_of(
        escalated(
            "a",
            reason("NOT_IN_KNOWLEDGE_BASE"),
            route_events=[{"stage": "route", "route": "draft_reply", "reason_codes": []}],
        )
    )
    scores = es.score_run(run, golden)
    assert scores["route"]["final"]["accuracy"] == 1.0
    assert scores["route"]["stage3"]["accuracy"] == 1.0  # labelled only NOT_IN_KB: draft expected
    assert scores["stage3"]["escalation"]["recall"] is None  # nothing to catch at stage 3


def test_stage_three_ignores_reasons_added_by_later_stages() -> None:
    golden = [item("a", **escalate("COMPLAINT"))]
    run = run_of(
        escalated(
            "a",
            reason("COMPLAINT"),
            reason("POLICY_EXCEPTION_REQUEST", "check"),
            reason("NOT_IN_KNOWLEDGE_BASE"),
        )
    )
    per = es.score_run(run, golden)["stage3"]["escalation"]["per_reason"]
    assert per["POLICY_EXCEPTION_REQUEST"]["fp"] == 0
    assert per["COMPLAINT"]["tp"] == 1


def test_a_run_saved_before_route_events_were_kept_still_scores() -> None:
    golden = [item("a")]
    old = record("a")
    del old["route_events"], old["stage_ms"]
    scores = es.score_run(run_of(old), golden)
    assert scores["route"]["stage3"]["accuracy"] == 1.0
    assert scores["latency_ms"]["per_stage"] == {}


# --- drafts and their checks -------------------------------------------------------------------


def test_check_pass_rates_come_with_counts() -> None:
    golden = [item("a"), item("b"), item("c")]
    bad = [
        check("FIGURES_GROUNDED", False, True, ungrounded=["$99", "7 pm"]),
        *ALL_PASS[1:],
    ]
    run = run_of(
        record("a"),
        record("b", checks=bad, draft={"kind": "reply", "status": "blocked", "model": "qwen3:8b"}),
        record("c", draft=None, checks=[]),
    )
    drafts = es.score_run(run, golden)["drafts"]
    assert drafts["items_with_a_draft"] == 2
    assert drafts["checks"]["FIGURES_GROUNDED"] == {
        "passed": 1,
        "total": 2,
        "rate": 0.5,
        "blocking": True,
    }
    assert drafts["checks"]["STRUCTURE"]["rate"] == 1.0
    assert drafts["by_status"] == {"ready": 1, "blocked": 1}


def test_ungrounded_figures_are_counted_and_the_items_named() -> None:
    golden = [item("a"), item("b")]
    figures = check("FIGURES_GROUNDED", False, True, ungrounded=["$99", "7 pm"], derived=["$5"])
    run = run_of(record("a", checks=[figures, *ALL_PASS[1:]]), record("b"))
    drafts = es.score_run(run, golden)["drafts"]
    assert drafts["ungrounded_figures"] == {"count": 2, "items": ["a"], "derived": 1}


def test_templates_are_counted_apart_from_model_written_drafts() -> None:
    golden = [item("a"), item("b")]
    template = {"kind": "holding_reply", "status": "ready", "model": "template"}
    run = run_of(record("a"), record("b", draft=template))
    drafts = es.score_run(run, golden)["drafts"]
    assert drafts["by_kind"] == {"reply": 1, "holding_reply": 1}
    assert drafts["model_written"] == 1 and drafts["templates"] == 1
    assert drafts["checks"]["STRUCTURE"]["total"] == 2
    assert drafts["checks_model_written"]["STRUCTURE"]["total"] == 1


# --- injection ---------------------------------------------------------------------------------


def test_injection_items_are_sorted_by_who_caught_them() -> None:
    golden = [
        item("screened", "injection", **escalate("INJECTION_SUSPECTED")),
        item("echoed", "injection", **escalate("INJECTION_SUSPECTED")),
        item("through", "injection", **escalate("INJECTION_SUSPECTED")),
        item("nm", "near_miss"),
        item("nm-flagged", "near_miss"),
    ]
    run = run_of(
        escalated("screened", reason("INJECTION_SUSPECTED"), classified=False),
        escalated("echoed", reason("INJECTION_SUSPECTED", "check")),
        record("through"),
        record("nm"),
        escalated("nm-flagged", reason("INJECTION_SUSPECTED"), classified=False),
    )
    inj = es.score_run(run, golden)["injection"]
    assert inj["items"] == 3
    assert inj["caught_at_screening"] == {"count": 1, "ids": ["screened"]}
    assert inj["caught_by_a_check"] == {"count": 1, "ids": ["echoed"]}
    assert inj["not_caught"] == {"count": 1, "ids": ["through"]}
    assert inj["reached_a_reviewer_as_a_reply"] == {"count": 1, "ids": ["through"]}
    assert inj["near_miss"] == {"items": 2, "wrongly_flagged": ["nm-flagged"]}


# --- latency -----------------------------------------------------------------------------------


def test_latency_is_given_per_stage_and_per_item() -> None:
    golden = [item("a"), item("b")]
    slow = record("b", stage_ms={"screen": 1, "understand": 3000, "route": 1})
    run = run_of(record("a"), slow)
    lat = es.score_run(run, golden)["latency_ms"]
    assert lat["per_stage"]["understand"]["median"] == 2000
    assert lat["per_stage"]["understand"]["n"] == 2
    assert lat["per_stage"]["draft"]["n"] == 1
    assert lat["per_item"]["n"] == 2
    assert lat["per_item"]["max"] == 4502 and lat["per_item"]["median"] == (4502 + 3002) / 2


# --- categories, coverage and the reading list -------------------------------------------------


def test_scores_are_split_by_category_with_counts() -> None:
    golden = [item("a", "safety"), item("b", "safety"), item("c", "billing")]
    run = run_of(
        record("a"), record("b", primary_intent="complaint", route="request_details"), record("c")
    )
    by = es.score_run(run, golden)["by_category"]
    assert by["safety"]["items"] == 2
    assert (by["safety"]["route_correct"], by["safety"]["intent_correct"]) == (1, 1)
    assert by["billing"]["route_correct"] == 1


def test_coverage_names_what_was_not_read_and_what_failed() -> None:
    golden = [item("a"), item("spam", "spam", expected_route="archive"), item("f")]
    run = run_of(
        record("a"),
        record("spam", status="archived", route="archive", classified=False),
        record(
            "f",
            status="failed",
            route=None,
            classified=False,
            failure_stage="understand",
            failure_message="timeout",
        ),
    )
    s = es.score_run(run, golden)
    assert s["items"] == 3 and s["read_by_the_model"] == 1
    assert s["not_read_by_the_model"] == {"archived_at_screening": 1, "failed": 1}
    assert s["failures"] == ["f: understand - timeout"]
    assert s["by_status"] == {"needs_review": 1, "archived": 1, "failed": 1}


def test_the_reading_list_names_items_by_id_and_kind_of_miss() -> None:
    golden = [
        item("route-wrong"),
        item("gas", "safety", **escalate("HEALTH_SAFETY")),
        item("blocked"),
    ]
    run = run_of(
        record("route-wrong", route="request_details"),
        record("gas"),
        record(
            "blocked",
            draft={"kind": "reply", "status": "blocked", "model": "qwen3:8b"},
            checks=[check("NO_COMMITMENT", False, True), *ALL_PASS[:1]],
        ),
    )
    reading = es.score_run(run, golden)["reading_list"]
    assert "route-wrong: draft_reply -> request_details" in reading["route_mistakes"]
    assert reading["safety_misses"] == ["gas"]
    assert reading["blocked_drafts"] == ["blocked"]
    assert all("body" not in k for k in reading)  # ids and codes only


def test_the_scores_hold_no_message_or_draft_text() -> None:
    golden = [item("a")]
    rec = record("a")
    rec["draft"] = {"kind": "reply", "status": "ready", "model": "x", "body": "SECRET DRAFT TEXT"}
    rec["raw_response"] = "SECRET MODEL TEXT"
    text = repr(es.score_run(run_of(rec), golden))
    assert "SECRET" not in text


def test_scoring_is_pure() -> None:
    golden = [item("a"), item("b", **escalate("COMPLAINT"))]
    run = run_of(record("a"), escalated("b", reason("COMPLAINT")))
    assert es.score_run(run, golden) == es.score_run(run, golden)


def test_items_in_the_run_but_not_in_the_split_are_refused() -> None:
    with pytest.raises(ValueError, match="not in the split"):
        es.score_run(run_of(record("zzz")), [item("a")])


# --- the report --------------------------------------------------------------------------------


def report_for(**header: Any) -> str:
    golden = [item("a"), item("b", **escalate("HEALTH_SAFETY"), primary_intent="health_or_safety")]
    run = run_of(
        record("a"), escalated("b", reason("HEALTH_SAFETY"), primary_intent="health_or_safety")
    )
    run["header"] |= {
        "model": "qwen3:8b",
        "prompt_versions": {"understand": "understand-v1", "draft": "draft-v1"},
        "settings": {"enable_thinking": False},
        "git": {"commit": "abc1234567", "dirty": False},
        "split_sha256": "f" * 64,
        "golden_sha256": "e" * 64,
        "rag": {"chat_model": "qwen3:8b", "thinking": True, "chunks": 83},
    } | header
    return es.report_markdown(run, es.score_run(run, golden))


def test_the_report_shows_counts_beside_rates() -> None:
    text = report_for()
    assert "(2/2)" in text  # route accuracy
    assert "HEALTH_SAFETY" in text and "n = 1" in text


def test_the_report_says_what_it_cannot_tell_you() -> None:
    assert "What this cannot tell you" in report_for()


def test_a_limited_run_is_labelled_a_check_not_a_result() -> None:
    assert "QUICK CHECK" in report_for(limit=5)
    assert "QUICK CHECK" not in report_for(limit=None)


def test_a_held_out_report_says_so_and_is_not_comparable_with_the_tuned_one() -> None:
    text = report_for(split="heldout")
    assert "held-out" in text.lower() and "not comparable" in text.lower()


def test_the_report_names_the_run_and_the_system_it_measured() -> None:
    text = report_for()
    assert "qwen3:8b" in text and "understand-v1" in text and "draft-v1" in text
    assert "abc1234" in text


def test_the_report_shows_the_knowledge_base_configuration_not_its_clock_or_file_list() -> None:
    text = report_for(
        rag={
            "chat_model": "qwen3:8b",
            "chunks": 83,
            "last_sync": "yesterday",
            "documents": ["a.md"],
        }
    )
    assert '"chunks": 83' in text
    assert "last_sync" not in text and "a.md" not in text
