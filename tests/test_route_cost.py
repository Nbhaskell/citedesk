"""The cost-weighted route score (tools/route_cost.py, D-094).

All items here are invented fixtures built in the tests. No test reads the real golden set.
"""

import json
from pathlib import Path

import pytest

from tools import route_cost as rc


def labels(route: str, reasons: list[str] | None = None) -> dict:
    return {"expected_route": route, "expected_reason_codes": reasons or []}


@pytest.mark.parametrize(
    ("wanted", "reasons", "got", "kind"),
    [
        ("escalate", ["HEALTH_SAFETY"], "escalate", "right"),
        ("escalate", ["HEALTH_SAFETY"], "draft_reply", "missed_safety"),
        ("escalate", ["HEALTH_SAFETY"], "archive", "missed_safety"),
        ("draft_reply", [], "archive", "lost_message"),
        ("escalate", ["COMPLAINT"], "archive", "lost_message"),
        ("escalate", ["COMPLAINT"], "draft_reply", "missed_escalation"),
        ("escalate", ["LEGAL_THREAT"], "request_details", "missed_escalation"),
        ("draft_reply", [], "escalate", "extra_escalation"),
        ("request_details", [], "escalate", "extra_escalation"),
        ("archive", [], "escalate", "spam_kept"),
        ("archive", [], "draft_reply", "spam_kept"),
        ("draft_reply", [], "request_details", "wrong_kind_of_reply"),
        ("request_details", [], "draft_reply", "wrong_kind_of_reply"),
        ("draft_reply", [], None, "extra_escalation"),  # failed: a person handles it
        ("escalate", ["COMPLAINT"], None, "right"),
        ("archive", [], "archive", "right"),
    ],
)
def test_each_outcome_falls_in_one_kind(
    wanted: str, reasons: list[str], got: str | None, kind: str
) -> None:
    assert rc.outcome(labels(wanted, reasons), got) == kind


def test_every_kind_has_a_cost_and_the_safety_miss_costs_most() -> None:
    assert set(rc.COSTS) == set(rc.KINDS) - {"right"}
    assert max(rc.COSTS.values()) == rc.COSTS["missed_safety"]
    assert min(rc.COSTS.values()) > 0


def test_a_run_is_costed_per_hundred_items() -> None:
    gold = {
        "a": labels("escalate", ["HEALTH_SAFETY"]),
        "b": labels("draft_reply"),
        "c": labels("archive"),
        "d": labels("draft_reply"),
    }
    routes = {"a": "escalate", "b": "escalate", "c": "escalate", "d": "draft_reply"}
    result = rc.cost(gold, routes)
    assert result["n"] == 4
    assert result["counts"]["extra_escalation"] == 1 and result["counts"]["spam_kept"] == 1
    expected = rc.COSTS["extra_escalation"] + rc.COSTS["spam_kept"]
    assert result["total"] == expected
    assert result["per_100"] == pytest.approx(expected * 100 / 4)


def test_the_simple_policies_are_costed_on_the_same_items() -> None:
    gold = {"a": labels("escalate", ["HEALTH_SAFETY"]), "b": labels("draft_reply")}
    everything_escalated = rc.cost(gold, rc.policy(gold, "escalate"))
    everything_drafted = rc.cost(gold, rc.policy(gold, "draft_reply"))
    assert everything_escalated["counts"]["extra_escalation"] == 1
    assert everything_escalated["counts"]["missed_safety"] == 0
    assert everything_drafted["counts"]["missed_safety"] == 1


def test_break_even_is_the_missed_escalation_cost_that_matches_escalating_everything() -> None:
    gold = {
        "a": labels("escalate", ["COMPLAINT"]),
        "b": labels("draft_reply"),
        "c": labels("draft_reply"),
        "d": labels("draft_reply"),
    }
    run = rc.cost(gold, {"a": "draft_reply", "b": "draft_reply", "c": "draft_reply", "d": "x"})
    everything = rc.cost(gold, rc.policy(gold, "escalate"))  # 3 extra escalations: 12
    # the run: one missed escalation (m) and one wrong kind of reply (1); m + 1 = 12 at m = 11
    assert rc.break_even(run, everything) == pytest.approx(11.0)
    assert rc.break_even(everything, everything) is None


def test_items_missing_from_the_run_are_refused() -> None:
    with pytest.raises(ValueError, match="not in the run"):
        rc.cost({"a": labels("draft_reply")}, {})


def test_a_sealed_item_is_refused() -> None:
    with pytest.raises(ValueError, match="sealed"):
        rc.labels_for([{"id": "x", "split": "sealed", "labels": labels("archive")}], "sealed")


def test_the_report_holds_ids_and_counts_but_no_message_text(tmp_path: Path) -> None:
    marker = "UNIQUE-MESSAGE-WORDS-12345"
    items = [
        {"id": "a", "split": "heldout", "body": marker, "labels": labels("draft_reply")},
        {"id": "b", "split": "heldout", "body": marker, "labels": labels("archive")},
    ]
    golden = tmp_path / "golden.json"
    golden.write_text(json.dumps({"header": {}, "items": items}), encoding="utf-8")
    run = tmp_path / "x.run.json"
    run.write_text(
        json.dumps(
            {
                "header": {"run_id": "x"},
                "items": [
                    {"id": "a", "route": "escalate", "reasons": []},
                    {"id": "b", "route": "archive", "reasons": []},
                ],
            }
        ),
        encoding="utf-8",
    )
    report = tmp_path / "report.md"
    code = rc.main(["--golden", str(golden), "--split", "heldout", "--md", str(report), str(run)])
    assert code == 0
    text = report.read_text(encoding="utf-8")
    assert marker not in text
    assert "Escalate everything" in text and "ASSUMPTION" in text
