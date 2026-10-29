"""The held-out ledger: one evaluation of one fixed system, with its passes declared up front."""

import json
from pathlib import Path
from typing import Any

import pytest

from tools import eval_ledger as ledger_mod
from tools.eval_ledger import LedgerRefused

NOW = "2026-10-30T09:00:00+00:00"
LATER = "2026-10-30T10:00:00+00:00"


def identity(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "code_tree": "a" * 40,
        "universe_tree": "b" * 40,
        "model": "qwen3:8b",
        "prompt_versions": {"understand": "understand-v1", "draft": "draft-v1"},
        "settings": {"enable_thinking": False},
        "rag": {"chat_model": "qwen3:8b", "thinking": True, "chunks": 83},
        "split_sha256": "c" * 64,
    }
    return base | over


def start(
    ledger: dict[str, Any], run_id: str, who: dict[str, Any] | None = None, **kw: Any
) -> ledger_mod.Authorization:
    who = who or identity()
    auth = ledger_mod.authorize(ledger, who, **kw)
    ledger_mod.record_start(
        ledger, auth, who, run_id=run_id, run_file=f"{run_id}.run.json", now=NOW
    )
    return auth


# --- what makes a system the same system -------------------------------------------------------


def test_the_same_identity_gives_the_same_id() -> None:
    assert ledger_mod.system_id(identity()) == ledger_mod.system_id(identity())


@pytest.mark.parametrize(
    "change",
    [
        {"code_tree": "d" * 40},
        {"universe_tree": "d" * 40},
        {"model": "qwen3:14b"},
        {"prompt_versions": {"understand": "understand-v2", "draft": "draft-v1"}},
        {"settings": {"enable_thinking": True}},
        {"rag": {"chat_model": "qwen3:8b", "thinking": False, "chunks": 83}},
        {"split_sha256": "d" * 64},
    ],
)
def test_changing_anything_about_the_system_changes_the_id(change: dict[str, Any]) -> None:
    assert ledger_mod.system_id(identity(**change)) != ledger_mod.system_id(identity())


def test_the_order_keys_are_written_in_does_not_matter() -> None:
    a = {"x": 1, "y": {"b": 1, "a": 2}}
    b = {"y": {"a": 2, "b": 1}, "x": 1}
    assert ledger_mod.system_id(a) == ledger_mod.system_id(b)


# --- the first run declares its passes ---------------------------------------------------------


def test_the_first_held_out_run_must_declare_how_many_passes() -> None:
    with pytest.raises(LedgerRefused, match="declare"):
        ledger_mod.authorize(ledger_mod.empty(), identity())


@pytest.mark.parametrize("passes", [0, 6, -1])
def test_declared_passes_are_between_one_and_five(passes: int) -> None:
    with pytest.raises(LedgerRefused, match="between 1 and 5"):
        ledger_mod.authorize(ledger_mod.empty(), identity(), passes=passes)


def test_the_first_run_is_pass_one_and_is_recorded_when_it_starts() -> None:
    ledger = ledger_mod.empty()
    auth = start(ledger, "r1", passes=3)
    assert auth.pass_number == 1 and not auth.outside_plan
    [evaluation] = ledger["evaluations"]
    assert evaluation["passes_declared"] == 3
    assert evaluation["system_id"] == ledger_mod.system_id(identity())
    assert evaluation["runs"][0]["status"] == "started"
    assert evaluation["runs"][0]["pass"] == 1


# --- passes of the same system -----------------------------------------------------------------


def finish(ledger: dict[str, Any], run_id: str) -> None:
    ledger_mod.record_finish(ledger, run_id, now=LATER, items=76, failed=0)


def test_declared_passes_follow_one_another_without_a_reason() -> None:
    ledger = ledger_mod.empty()
    start(ledger, "r1", passes=2)
    finish(ledger, "r1")
    second = start(ledger, "r2")
    assert second.pass_number == 2 and not second.outside_plan
    finish(ledger, "r2")
    assert [r["status"] for r in ledger["evaluations"][0]["runs"]] == ["completed", "completed"]


def test_a_pass_beyond_the_declared_ones_is_refused() -> None:
    ledger = ledger_mod.empty()
    start(ledger, "r1", passes=1)
    finish(ledger, "r1")
    with pytest.raises(LedgerRefused, match="1 of 1"):
        ledger_mod.authorize(ledger, identity())


def test_an_extra_pass_needs_a_written_reason_and_is_marked() -> None:
    ledger = ledger_mod.empty()
    start(ledger, "r1", passes=1)
    finish(ledger, "r1")
    reason = "the first pass lost its last 5 items to a model timeout"
    auth = start(ledger, "r2", justify=reason)
    assert auth.outside_plan and auth.pass_number == 2
    assert ledger["evaluations"][0]["runs"][1]["justification"] == reason
    assert ledger["evaluations"][0]["runs"][1]["outside_plan"] is True


def test_a_reason_that_is_too_short_does_not_count() -> None:
    ledger = ledger_mod.empty()
    start(ledger, "r1", passes=1)
    finish(ledger, "r1")
    with pytest.raises(LedgerRefused, match="reason"):
        ledger_mod.authorize(ledger, identity(), justify="again")


def test_a_run_that_never_finished_blocks_a_fresh_start() -> None:
    ledger = ledger_mod.empty()
    start(ledger, "r1", passes=3)
    with pytest.raises(LedgerRefused, match="resume"):
        ledger_mod.authorize(ledger, identity())


def test_an_unfinished_run_can_be_resumed_without_using_a_pass() -> None:
    ledger = ledger_mod.empty()
    start(ledger, "r1", passes=3)
    auth = ledger_mod.authorize(ledger, identity(), resume_run_id="r1")
    assert auth.resume and auth.pass_number == 1
    ledger_mod.record_start(
        ledger, auth, identity(), run_id="r1", run_file="r1.run.json", now=LATER
    )
    assert len(ledger["evaluations"][0]["runs"]) == 1


def test_a_finished_run_cannot_be_resumed() -> None:
    ledger = ledger_mod.empty()
    start(ledger, "r1", passes=3)
    finish(ledger, "r1")
    with pytest.raises(LedgerRefused, match="not an unfinished"):
        ledger_mod.authorize(ledger, identity(), resume_run_id="r1")


def test_a_run_nobody_recorded_cannot_be_resumed() -> None:
    with pytest.raises(LedgerRefused, match="not an unfinished"):
        ledger_mod.authorize(ledger_mod.empty(), identity(), resume_run_id="ghost")


def test_resuming_with_a_changed_system_is_refused() -> None:
    ledger = ledger_mod.empty()
    start(ledger, "r1", passes=3)
    with pytest.raises(LedgerRefused, match="different system"):
        ledger_mod.authorize(ledger, identity(model="other"), resume_run_id="r1")


def test_declaring_a_different_number_of_passes_later_is_refused() -> None:
    ledger = ledger_mod.empty()
    start(ledger, "r1", passes=3)
    finish(ledger, "r1")
    with pytest.raises(LedgerRefused, match="declared 3"):
        ledger_mod.authorize(ledger, identity(), passes=5)


# --- a changed system has already had its one look ---------------------------------------------


def test_a_different_system_after_a_held_out_run_needs_a_reason() -> None:
    ledger = ledger_mod.empty()
    start(ledger, "r1", passes=1)
    finish(ledger, "r1")
    changed = identity(code_tree="e" * 40)
    with pytest.raises(LedgerRefused, match="spent"):
        ledger_mod.authorize(ledger, changed, passes=1)


def test_a_different_system_with_a_reason_is_a_new_marked_evaluation() -> None:
    ledger = ledger_mod.empty()
    start(ledger, "r1", passes=1)
    finish(ledger, "r1")
    changed = identity(code_tree="e" * 40)
    reason = "owner asked for a rerun after fixing a crash in the check stage"
    auth = start(ledger, "r2", who=changed, passes=1, justify=reason)
    assert auth.outside_plan
    assert len(ledger["evaluations"]) == 2
    assert ledger["evaluations"][1]["runs"][0]["justification"] == reason


# --- finishing, saving, and the shape on disk --------------------------------------------------


def test_finishing_records_the_item_and_failure_counts() -> None:
    ledger = ledger_mod.empty()
    start(ledger, "r1", passes=1)
    ledger_mod.record_finish(ledger, "r1", now=LATER, items=76, failed=2)
    run = ledger["evaluations"][0]["runs"][0]
    assert (run["status"], run["items"], run["failed"], run["finished_at"]) == (
        "completed",
        76,
        2,
        LATER,
    )


def test_finishing_an_unknown_run_is_an_error() -> None:
    with pytest.raises(KeyError):
        ledger_mod.record_finish(ledger_mod.empty(), "ghost", now=LATER, items=0, failed=0)


def test_a_missing_ledger_file_is_an_empty_ledger(tmp_path: Path) -> None:
    assert ledger_mod.load(tmp_path / "none.json") == ledger_mod.empty()


def test_the_ledger_round_trips_through_a_file(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    ledger = ledger_mod.empty()
    start(ledger, "r1", passes=2)
    ledger_mod.save(path, ledger)
    assert ledger_mod.load(path) == ledger
    assert json.loads(path.read_text("utf-8"))["format"] == "heldout-ledger-v1"


def test_a_file_that_is_not_a_ledger_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    path.write_text('{"format": "something-else"}', encoding="utf-8")
    with pytest.raises(LedgerRefused, match="not a held-out ledger"):
        ledger_mod.load(path)


def test_the_ledger_holds_no_message_text() -> None:
    ledger = ledger_mod.empty()
    start(ledger, "r1", passes=1)
    assert set(ledger["evaluations"][0]) == {
        "system_id",
        "identity",
        "passes_declared",
        "created_at",
        "runs",
    }


# --- the checks made before any held-out item is read ------------------------------------------


def request(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "allow_heldout": True,
        "limit": None,
        "dirty": False,
        "git_known": True,
    }
    return base | over


def test_a_held_out_request_without_the_flag_is_refused() -> None:
    problems = ledger_mod.heldout_problems(**request(allow_heldout=False))
    assert problems and "--allow-heldout" in problems[0]


def test_a_partial_held_out_run_is_refused() -> None:
    assert any("--limit" in p for p in ledger_mod.heldout_problems(**request(limit=5)))


def test_a_held_out_run_on_uncommitted_changes_is_refused() -> None:
    assert any("uncommitted" in p for p in ledger_mod.heldout_problems(**request(dirty=True)))


def test_a_held_out_run_without_git_is_refused() -> None:
    assert any("git" in p for p in ledger_mod.heldout_problems(**request(git_known=False)))


def test_a_clean_flagged_full_request_has_no_problems() -> None:
    assert ledger_mod.heldout_problems(**request()) == []


def test_the_tuned_split_needs_none_of_this() -> None:
    assert ledger_mod.heldout_problems(**request(allow_heldout=False), split="tuned") == []
