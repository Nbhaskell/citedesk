"""The Phase 4 scoring script, tested with hand-made runs and a scripted model.

What the real model scores is the script's output, not something asserted here.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from citedesk.config import Settings
from citedesk.providers import FakeLLM
from citedesk.screening import screen
from tests.helpers import perfect_reply
from tools import score_understanding as su

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN = json.loads((REPO_ROOT / "eval/golden/citedesk_v1.json").read_text("utf-8"))
TUNED = [item for item in GOLDEN["items"] if item["split"] == "tuned"]


# --- what the labels imply before retrieval ----------------------------------------------------


def labels(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "expected_route": "draft_reply",
        "expected_reason_codes": [],
    }
    return base | over


def test_an_ordinary_item_expects_what_it_is_labelled_with() -> None:
    assert su.expected_outcome(labels()) == ("draft_reply", [])
    assert su.expected_outcome(
        labels(expected_route="escalate", expected_reason_codes=["COMPLAINT"])
    ) == ("escalate", ["COMPLAINT"])


def test_an_item_labelled_only_not_in_knowledge_base_expects_a_draft_for_now() -> None:
    wanted = labels(expected_route="escalate", expected_reason_codes=["NOT_IN_KNOWLEDGE_BASE"])
    assert su.expected_outcome(wanted) == ("draft_reply", [])


def test_an_injection_item_expects_only_what_screening_can_see() -> None:
    wanted = labels(
        expected_route="escalate",
        expected_reason_codes=["INJECTION_SUSPECTED", "REFUND_OR_DISPUTE"],
    )
    assert su.expected_outcome(wanted) == ("escalate", ["INJECTION_SUSPECTED"])
    with_gas = labels(
        expected_route="escalate", expected_reason_codes=["INJECTION_SUSPECTED", "HEALTH_SAFETY"]
    )
    assert su.expected_outcome(with_gas)[1] == ["INJECTION_SUSPECTED", "HEALTH_SAFETY"]


# --- comparing fields --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        ("unknown", None),
        ("Unknown", None),
        ("  Alderbrook   Heights. ", "alderbrook heights"),
        ("2026-11-06", "2026-11-06"),
        ("KH-4471", "kh-4471"),
        ("drain_cleaning", "drain_cleaning"),
    ],
)
def test_values_are_compared_after_tidying(value: Any, expected: str | None) -> None:
    assert su.normalise_value(value) == expected


def test_the_area_has_a_lenient_match_where_one_contains_the_other() -> None:
    assert su.same_area("alderbrook", "alderbrook heights")
    assert su.same_area("alderbrook heights", "alderbrook")
    assert not su.same_area("millrace", "alderbrook heights")
    assert su.same_area(None, None)
    assert not su.same_area("millrace", None)


# --- the scores, on a small run whose answers are known ----------------------------------------


def item(item_id: str, **label_over: Any) -> dict[str, Any]:
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
    return {"id": item_id, "split": "tuned", "labels": labels | label_over}


def record(item_id: str, **over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": item_id,
        "status": "routed",
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
    }
    return base | over


def run_of(*records: dict[str, Any]) -> dict[str, Any]:
    return {"header": {}, "items": list(records)}


def test_intent_accuracy_counts_only_items_the_model_read() -> None:
    items = [
        item("a"),
        item("b"),
        item("c", intents=["spam"], primary_intent="spam", expected_route="archive"),
    ]
    run = run_of(
        record("a"),
        record(
            "b", primary_intent="complaint", intents=[{"intent": "complaint", "confidence": "high"}]
        ),
        record("c", status="archived", route="archive", classified=False, primary_intent=None),
    )
    scores = su.score_run(run, items)
    assert scores["read_by_the_model"] == 2
    assert scores["not_read_by_the_model"] == {"archived_at_screening": 1}
    assert scores["intent"]["primary_accuracy"] == 0.5
    assert scores["intent"]["wrong"] == ["b: pricing_question -> complaint"]


def test_field_scores_separate_missed_from_invented() -> None:
    items = [
        item(
            "a",
            fields={
                "service_type": "water_heater",
                "start_date": "2026-11-06",
                "property_type": "house",
                "address_area": "Alderbrook Heights",
            },
        ),
        item("b"),
    ]
    run = run_of(
        record(
            "a",
            fields={
                "service_type": "water_heater",
                "start_date": None,  # missed
                "property_type": "house",
                "address_area": "Alderbrook",  # close, not exact
                "booking_reference": None,
            },
        ),
        record(
            "b",
            fields={
                "service_type": "drain_cleaning",
                "start_date": "2026-11-09",  # invented
                "property_type": "unknown",
                "address_area": None,
                "booking_reference": None,
            },
        ),
    )
    fields = su.score_run(run, items)["fields"]["per_field"]
    assert fields["service_type"]["accuracy"] == 1.0
    assert fields["start_date"]["accuracy"] == 0.0
    assert fields["start_date"]["recall_when_present"] == 0.0
    assert fields["start_date"]["spurious_when_absent"] == 1
    assert fields["property_type"]["accuracy"] == 1.0  # "unknown" counts as not given
    assert fields["address_area"]["accuracy"] == 0.5
    assert fields["address_area"]["lenient_accuracy"] == 1.0
    overall = su.score_run(run, items)["fields"]
    assert overall["accuracy"] == pytest.approx((2 + 0 + 2 + 1 + 2) / 10)
    assert overall["items_with_every_field_right"] == 0.0


def escalating(item_id: str, *codes: str) -> dict[str, Any]:
    return item(
        item_id, expected_route="escalate", should_escalate=True, expected_reason_codes=list(codes)
    )


def test_escalation_precision_and_recall() -> None:
    items = [
        escalating("caught", "COMPLAINT"),
        escalating("missed", "LEGAL_THREAT"),
        item("quiet"),
        item("over"),
    ]
    run = run_of(
        record(
            "caught",
            route="escalate",
            status="escalated",
            reasons=[{"code": "COMPLAINT", "source": "rule"}],
        ),
        record("missed"),
        record("quiet"),
        record(
            "over",
            route="escalate",
            status="escalated",
            reasons=[{"code": "LOW_CONFIDENCE", "source": "rule"}],
        ),
    )
    esc = su.score_run(run, items)["escalation"]
    assert esc["confusion"] == {"tp": 1, "fp": 1, "fn": 1, "tn": 1}
    assert esc["precision"] == 0.5 and esc["recall"] == 0.5
    assert esc["false_positives"] == ["over"] and esc["false_negatives"] == ["missed"]
    assert esc["per_reason"]["COMPLAINT"]["recall"] == 1.0
    assert esc["per_reason"]["LEGAL_THREAT"]["missed"] == ["missed"]
    assert esc["per_reason"]["LOW_CONFIDENCE"]["extra"] == ["over"]


def test_an_item_the_knowledge_base_would_decline_is_not_a_missed_escalation_yet() -> None:
    items = [escalating("later", "NOT_IN_KNOWLEDGE_BASE")]
    esc = su.score_run(run_of(record("later")), items)["escalation"]
    assert esc["confusion"]["fn"] == 0
    assert su.score_run(run_of(record("later")), items)["route"]["accuracy"] == 1.0


def test_an_injection_item_is_scored_on_the_reasons_screening_can_see() -> None:
    items = [escalating("trick", "INJECTION_SUSPECTED", "REFUND_OR_DISPUTE")]
    run = run_of(
        record(
            "trick",
            status="escalated",
            route="escalate",
            classified=False,
            reasons=[{"code": "INJECTION_SUSPECTED", "source": "rule"}],
        )
    )
    esc = su.score_run(run, items)["escalation"]
    assert esc["recall"] == 1.0
    assert esc["per_reason"]["REFUND_OR_DISPUTE"]["fn"] == 0
    assert esc["per_reason"]["INJECTION_SUSPECTED"]["recall"] == 1.0


def test_a_failed_item_is_listed_and_counts_against_routing() -> None:
    items = [item("broken")]
    run = run_of(
        record(
            "broken",
            status="failed",
            route=None,
            classified=False,
            failure_stage="understand",
            failure_message="The model gave no usable reply (timeout)",
        )
    )
    scores = su.score_run(run, items)
    assert scores["not_read_by_the_model"] == {"failed": 1}
    assert scores["failures"] == ["broken: understand - The model gave no usable reply (timeout)"]
    assert scores["route"]["accuracy"] == 0.0


def test_who_caught_each_safety_item_is_reported() -> None:
    items = [escalating(name, "HEALTH_SAFETY") for name in ("both", "model", "net", "none")]
    health = [{"intent": "health_or_safety", "confidence": "high"}]
    run = run_of(
        record("both", intents=health, safety_net_hit=True),
        record("model", intents=health),
        record("net", safety_net_hit=True),
        record("none"),
    )
    who = su.score_run(run, items)["safety_net"]["safety_items_by_who_caught_them"]
    assert who == {"both": 1, "model_only": 1, "net_only": 1, "neither": 1}


def test_urgency_is_scored_with_and_without_the_net() -> None:
    items = [item("a", urgency="urgent")]
    run = run_of(record("a", urgency="high", model_urgency="normal"))
    urgency = su.score_run(run, items)["urgency"]
    assert urgency["accuracy"] == 0.0 and urgency["model_alone_accuracy"] == 0.0
    assert urgency["wrong"] == ["a: urgent -> high"]


def test_timing_and_retries_are_summarised() -> None:
    items = [item("a"), item("b"), item("c")]
    run = run_of(
        record("a", model_ms=1000),
        record("b", model_ms=3000, attempts=2),
        record("c", model_ms=2000),
    )
    scores = su.score_run(run, items)
    assert scores["retried"] == 1
    assert scores["latency_ms"] == {"median": 2000, "p90": 2000, "max": 3000}


def test_scoring_is_repeatable_and_ignores_items_that_were_not_run() -> None:
    items = [item("a"), item("never_run")]
    run = run_of(record("a"))
    assert su.score_run(run, items) == su.score_run(run, items)
    assert su.score_run(run, items)["items"] == 1


def test_rates_over_nothing_are_not_a_number() -> None:
    assert su.ratio(0, 0) is None
    assert su.pct(None) == "n/a"
    assert su.pct(0.5) == "50.0%"


# --- the whole tuned split through the real pipeline with a model that knows the labels -------


def perfect_run() -> dict[str, Any]:
    # The model reads the stored (masked) text, so the lookup uses that.
    by_body = {
        screen(i.get("subject"), i["body"], spam_threshold=0.8).body.strip(): i for i in TUNED
    }
    llm = FakeLLM(lambda call: next(perfect_reply(i) for b, i in by_body.items() if b in call.user))
    return su.make_run(
        TUNED,
        Settings(_env_file=None),
        llm,
        split="tuned",
        reference_date=GOLDEN["header"]["reference_date"],
    )


@pytest.fixture(scope="module")
def run() -> dict[str, Any]:
    return perfect_run()


def test_a_perfect_reader_scores_perfectly_where_the_rules_allow(run: dict[str, Any]) -> None:
    scores = su.score_run(run, GOLDEN["items"])
    assert scores["items"] == len(TUNED) and scores["failures"] == []
    assert scores["intent"]["primary_accuracy"] == 1.0
    assert scores["route"]["accuracy"] == 1.0
    esc = scores["escalation"]
    assert esc["precision"] == 1.0 and esc["recall"] == 1.0
    assert esc["per_reason"]["HEALTH_SAFETY"]["extra"] == ["legal-sue-over-water-damage"]  # D-037
    assert all(r["missed"] == [] for r in esc["per_reason"].values())


def test_the_run_file_records_where_it_came_from(run: dict[str, Any]) -> None:
    header = run["header"]
    assert header["prompt_version"] == "understand-v1" and header["model"] == "fake-model"
    assert header["split"] == "tuned" and header["reference_date"] == "2026-10-28"
    assert len(header["golden_sha256"]) == 64 and header["settings"]["enable_thinking"] is True
    assert {"commit", "dirty"} <= set(header["git"])


def test_the_run_file_holds_no_message_text(run: dict[str, Any]) -> None:
    text = " ".join(json.dumps(run).lower().split())
    for entry in TUNED:
        words = " ".join(entry["body"].lower().split())
        windows = (words[i : i + 30] for i in range(0, max(1, len(words) - 29), 10))
        assert not any(window in text for window in windows), entry["id"]


def test_the_report_names_what_it_cannot_tell_you(run: dict[str, Any]) -> None:
    text = su.report(run, su.score_run(run, GOLDEN["items"]))
    for needle in (
        "Intent",
        "Fields",
        "Escalation",
        "precision",
        "recall",
        "What this cannot tell you",
    ):
        assert needle in text


# --- the command line --------------------------------------------------------------------------


def test_the_held_out_split_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    assert su.main(["--split", "heldout"]) == 2
    assert "Phase 7" in capsys.readouterr().err


def test_a_saved_run_can_be_scored_again_without_a_model(
    run: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    saved = tmp_path / "saved.run.json"
    saved.write_text(json.dumps(run), encoding="utf-8")
    assert su.main(["--from", str(saved)]) == 0
    assert "primary intent accuracy" in capsys.readouterr().out
    scores = json.loads((tmp_path / "saved.scores.json").read_text("utf-8"))
    assert scores["items"] == len(TUNED)
