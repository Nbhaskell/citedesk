"""Provenance helpers of the evaluation tools: split hashes, git state, knowledge base status."""

import json
from pathlib import Path
from typing import Any

import pytest

from tests.golden_data import tuned_golden
from tools import eval_common as ec


def item(item_id: str, split: str) -> dict[str, Any]:
    return {"id": item_id, "split": split, "body": f"message {item_id}", "labels": {"x": 1}}


GOLDEN = {"items": [item("a", "tuned"), item("b", "heldout"), item("c", "tuned")]}


def test_a_split_is_selected_in_file_order() -> None:
    assert [i["id"] for i in ec.select_split(GOLDEN, "tuned")] == ["a", "c"]
    assert [i["id"] for i in ec.select_split(GOLDEN, "heldout")] == ["b"]


def test_an_unknown_split_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown split"):
        ec.select_split(GOLDEN, "all")


def test_the_tuned_hash_does_not_move_when_held_out_items_are_added() -> None:
    before = ec.split_sha256(ec.select_split(GOLDEN, "tuned"))
    more = {"items": [*GOLDEN["items"], item("d", "heldout"), item("e", "heldout")]}
    assert ec.split_sha256(ec.select_split(more, "tuned")) == before


def test_the_split_hash_moves_when_a_label_or_a_message_does() -> None:
    items = ec.select_split(GOLDEN, "tuned")
    base = ec.split_sha256(items)
    relabelled = [{**items[0], "labels": {"x": 2}}, items[1]]
    reworded = [{**items[0], "body": "other"}, items[1]]
    assert ec.split_sha256(relabelled) != base
    assert ec.split_sha256(reworded) != base
    assert ec.split_sha256(list(reversed(items))) != base  # order is part of what was run


def test_the_hash_of_the_real_tuned_split_is_a_stable_64_hex_digest() -> None:
    first = ec.split_sha256(tuned_golden()["items"])
    assert first == ec.split_sha256(tuned_golden()["items"])
    assert len(first) == 64 and int(first, 16) >= 0


def test_a_json_file_is_written_whole_or_not_at_all(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "x.json"
    ec.write_json_atomic(path, {"a": 1})
    ec.write_json_atomic(path, {"a": 2})
    assert json.loads(path.read_text("utf-8")) == {"a": 2}
    assert not (tmp_path / "sub" / "x.json.tmp").exists()


# --- a tree with only evaluation files changed is not a changed system -------------------------


def test_changes_under_the_ledger_and_the_runs_do_not_make_the_tree_dirty() -> None:
    status = " M eval/heldout_ledger.json\n?? eval/runs/x.run.json\n?? eval/reports/r.md\n"
    assert ec.dirty_paths(status) == []


def test_a_change_to_the_system_makes_it_dirty() -> None:
    status = " M eval/heldout_ledger.json\n M citedesk/pipeline.py\n?? tools/new.py\n"
    assert ec.dirty_paths(status) == ["citedesk/pipeline.py", "tools/new.py"]


def test_a_renamed_file_is_listed_by_its_new_path() -> None:
    assert ec.dirty_paths("R  old.py -> citedesk/new.py\n") == ["citedesk/new.py"]


def test_git_state_names_the_commit_and_the_code_tree() -> None:
    state = ec.git_state()
    assert set(state) == {
        "commit",
        "dirty",
        "dirty_paths",
        "code_tree",
        "universe_tree",
    }
    assert state["code_tree"] is None or len(state["code_tree"]) == 40


# --- the knowledge base's status ---------------------------------------------------------------

STATUS = {
    "files": 8,
    "chunks": 83,
    "documents": ["a.md"],
    "last_sync": "2026-10-30T09:00:00",
    "last_change": "2026-10-30T08:00:00",
    "chat_model": "qwen3:8b",
    "embed_model": "embeddinggemma",
    "thinking": True,
    "split_search": False,
    "watching": False,
    "auth_required": False,
}


def test_the_status_keeps_configuration_and_drops_what_is_not_needed() -> None:
    got = ec.rag_status("http://127.0.0.1:8000", get=lambda url, t: STATUS)
    assert got["chat_model"] == "qwen3:8b" and got["chunks"] == 83
    assert "auth_required" not in got and "watching" not in got


def test_only_configuration_goes_into_the_identity_not_the_clock() -> None:
    got = ec.rag_status("http://127.0.0.1:8000", get=lambda url, t: STATUS)
    identity = ec.rag_identity(got)
    assert "last_sync" not in identity and "documents" not in identity
    assert identity["thinking"] is True and identity["embed_model"] == "embeddinggemma"


def test_a_status_that_cannot_be_read_is_a_code_not_a_crash() -> None:
    def down(url: str, timeout: float) -> dict[str, Any]:
        raise OSError("nothing there")

    assert ec.rag_status("http://127.0.0.1:8000", get=down) == {"error": "unavailable"}


def test_a_status_is_only_asked_of_this_machine() -> None:
    def never(url: str, timeout: float) -> dict[str, Any]:
        raise AssertionError("should not be contacted")

    assert ec.rag_status("http://example.com:8000", get=never) == {"error": "not_local"}
