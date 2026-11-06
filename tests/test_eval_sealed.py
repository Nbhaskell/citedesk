"""The lock on the sealed set (D-071): one confirmed evaluation of one fixed system, the file
checked against its committed hash, and every run written into a committed ledger first.

No test here reads the sealed set. The runs below use tuned items copied under the name "sealed" and
a hash check that is scripted, so the lock can be exercised without the real file.
"""

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from citedesk.config import Settings
from tests.golden_data import tuned_golden
from tests.test_eval_ledger import identity, start
from tests.test_eval_run import BUSINESS, GIT, ITEMS, RAG, kb, model_for
from tools import eval_common as ec
from tools import eval_ledger as ledger_mod
from tools import eval_run as er
from tools.eval_ledger import LedgerRefused
from tools.golden import SEALED_FILE

CONFIRM = ["--split", "sealed", "--confirm-sealed-once"]
FIRST = [*CONFIRM, "--sealed-passes", "1"]


def sealed_copy() -> dict[str, Any]:
    """Tuned items filed under the sealed name, so no real sealed item is touched."""
    items = copy.deepcopy(ITEMS[:6])
    for item in items:
        item["split"] = "sealed"
    return {"header": {"name": "x", "version": 1, "reference_date": "2026-10-28"}, "items": items}


def command(
    tmp_path: Path,
    argv: list[str],
    *,
    golden: dict[str, Any] | None = None,
    git: dict[str, Any] | None = None,
    hash_ok: bool = True,
    code_tree: str | None = None,
) -> int:
    golden = golden or sealed_copy()
    return er.run_command(
        er.parse_args(argv),
        golden=golden,
        golden_sha256="e" * 64,
        settings=Settings(_env_file=None),
        llm=model_for(golden["items"]),
        kb=kb(),
        business=BUSINESS,
        git=(git or GIT) | ({"code_tree": code_tree} if code_tree else {}),
        rag=RAG,
        runs_dir=tmp_path / "runs",
        ledger_path=tmp_path / "heldout.json",
        sealed_ledger_path=tmp_path / "sealed.json",
        preflight=lambda: None,
        sealed_hash_matches=lambda: hash_ok,
    )


def ledger_runs(tmp_path: Path) -> list[dict[str, Any]]:
    data = json.loads((tmp_path / "sealed.json").read_text("utf-8"))
    return [r for e in data["evaluations"] for r in e["runs"]]


# --- the rules in the ledger module ------------------------------------------------------------


def test_a_sealed_ledger_is_its_own_file_format_and_says_sealed() -> None:
    ledger = ledger_mod.empty("sealed")
    assert ledger["format"] == "sealed-ledger-v1" and "sealed" in ledger["note"]
    start(ledger, "a", passes=1)
    with pytest.raises(LedgerRefused, match="sealed"):
        ledger_mod.authorize(ledger, identity(code_tree="d" * 40))


def test_a_held_out_ledger_cannot_be_loaded_as_a_sealed_one(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    ledger_mod.save(path, ledger_mod.empty("heldout"))
    with pytest.raises(LedgerRefused, match="not a sealed ledger"):
        ledger_mod.load(path, "sealed")


def test_a_first_sealed_run_must_declare_its_passes_and_says_which_flag() -> None:
    with pytest.raises(LedgerRefused, match="--sealed-passes"):
        ledger_mod.authorize(ledger_mod.empty("sealed"), identity())


def test_the_sealed_requests_refused_before_anything_is_touched() -> None:
    bad = ledger_mod.sealed_problems(
        split="sealed",
        confirmed=False,
        limit=3,
        dirty=True,
        git_known=True,
        hash_matches=False,
    )
    text = " ".join(bad)
    assert "--confirm-sealed-once" in text and "--limit" in text
    assert "uncommitted" in text and "committed hash" in text
    assert (
        ledger_mod.sealed_problems(
            split="tuned", confirmed=False, limit=3, dirty=True, git_known=True, hash_matches=False
        )
        == []
    )
    assert (
        ledger_mod.sealed_problems(
            split="sealed",
            confirmed=True,
            limit=None,
            dirty=False,
            git_known=True,
            hash_matches=True,
        )
        == []
    )


# --- the command ---------------------------------------------------------------------------------


def test_without_the_confirmation_flag_nothing_is_written(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert command(tmp_path, ["--split", "sealed", "--sealed-passes", "1"]) == 2
    assert "--confirm-sealed-once" in capsys.readouterr().err
    assert not (tmp_path / "sealed.json").exists() and not (tmp_path / "runs").exists()


def test_a_file_that_does_not_match_its_hash_is_refused_before_any_item(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert command(tmp_path, FIRST, hash_ok=False) == 2
    assert "committed hash" in capsys.readouterr().err
    assert not (tmp_path / "sealed.json").exists() and not (tmp_path / "runs").exists()


def test_a_dirty_tree_or_a_limit_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert command(tmp_path, FIRST, git=GIT | {"dirty": True}) == 2
    assert command(tmp_path, [*FIRST, "--limit", "2"]) == 2
    assert not (tmp_path / "sealed.json").exists()
    assert "uncommitted" in capsys.readouterr().err


def test_the_first_run_must_declare_its_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert command(tmp_path, CONFIRM) == 2
    assert "--sealed-passes" in capsys.readouterr().err
    assert not (tmp_path / "runs").exists()


def test_a_confirmed_run_is_written_into_the_sealed_ledger_and_not_the_held_out_one(
    tmp_path: Path,
) -> None:
    assert command(tmp_path, FIRST) == 0
    runs = ledger_runs(tmp_path)
    assert [(r["pass"], r["status"], r["items"]) for r in runs] == [(1, "completed", 6)]
    assert not (tmp_path / "heldout.json").exists()
    saved = next((tmp_path / "runs").glob("eval-sealed-*.run.json"))
    assert json.loads(saved.read_text("utf-8"))["header"]["split"] == "sealed"


def test_the_ledger_has_the_run_before_the_first_item_is_read(tmp_path: Path) -> None:
    seen: dict[str, Any] = {}

    def watch(number: int, total: int, record: dict[str, Any]) -> None:
        if number == 1:
            seen["runs"] = ledger_runs(tmp_path)

    golden = sealed_copy()
    code = er.run_command(
        er.parse_args(FIRST),
        golden=golden,
        golden_sha256="e" * 64,
        settings=Settings(_env_file=None),
        llm=model_for(golden["items"]),
        kb=kb(),
        business=BUSINESS,
        git=GIT,
        rag=RAG,
        runs_dir=tmp_path / "runs",
        ledger_path=tmp_path / "heldout.json",
        sealed_ledger_path=tmp_path / "sealed.json",
        preflight=lambda: None,
        sealed_hash_matches=lambda: True,
        progress=watch,
    )
    assert code == 0
    assert seen["runs"][0]["status"] == "started"  # written before the item finished


def test_a_second_look_at_the_same_system_is_refused_without_a_written_reason(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert command(tmp_path, FIRST) == 0
    assert command(tmp_path, CONFIRM) == 2
    assert "all the passes declared" in capsys.readouterr().err
    assert len(ledger_runs(tmp_path)) == 1


def test_a_different_system_finds_the_sealed_set_spent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert command(tmp_path, FIRST) == 0
    assert command(tmp_path, FIRST, code_tree="f" * 40) == 2
    assert "different system" in capsys.readouterr().err


def test_a_written_reason_is_kept_in_the_ledger(tmp_path: Path) -> None:
    reason = "A rerun after the scorer was found to read one label wrongly."
    assert command(tmp_path, FIRST) == 0
    assert command(tmp_path, [*CONFIRM, "--justify", reason]) == 0
    runs = ledger_runs(tmp_path)
    assert len(runs) == 2 and runs[1]["outside_plan"] is True and runs[1]["justification"] == reason


def test_several_declared_passes_are_allowed(tmp_path: Path) -> None:
    argv = [*CONFIRM, "--sealed-passes", "2", "--passes", "2"]
    assert command(tmp_path, argv) == 0
    assert [r["pass"] for r in ledger_runs(tmp_path)] == [1, 2]


def test_a_tuned_run_never_touches_the_sealed_ledger_or_asks_for_the_flag(
    tmp_path: Path,
) -> None:
    golden = tuned_golden()
    golden = {"header": golden["header"], "items": golden["items"][:3]}
    assert command(tmp_path, ["--split", "tuned"], golden=golden) == 0
    assert not (tmp_path / "sealed.json").exists()


# --- the helpers ---------------------------------------------------------------------------------


def test_the_sealed_split_is_known_and_its_labels_come_from_the_sealed_file() -> None:
    assert "sealed" in ec.SPLITS and "sealed" in ec.LOCKED_SPLITS
    assert ec.golden_file_for("sealed") == SEALED_FILE
    assert ec.golden_file_for("tuned") == ec.GOLDEN_FILE
    assert ec.golden_file_for("heldout") == ec.GOLDEN_FILE


def test_a_change_to_the_sealed_ledger_does_not_make_the_tree_dirty() -> None:
    porcelain = " M eval/sealed_ledger.json\n M eval/heldout_ledger.json\n M citedesk/api.py\n"
    assert ec.dirty_paths(porcelain) == ["citedesk/api.py"]


# --- scoring and comparing a sealed run ------------------------------------------------------


def saved_sealed_run(tmp_path: Path) -> Path:
    assert command(tmp_path, FIRST) == 0
    return next((tmp_path / "runs").glob("eval-sealed-*.run.json"))


def test_a_sealed_run_is_scored_against_the_sealed_labels_and_says_what_it_is(
    tmp_path: Path,
) -> None:
    from tools import eval_score as es

    path = saved_sealed_run(tmp_path)
    one = es.load_pass(path, sealed_copy())
    text = es.report_markdown(one["run"], one["scores"])
    assert "**Sealed set.**" in text and "D-071" in text
    assert "fixed before any held-out result" not in text
    assert one["scores"]["items"] == 6


def test_the_labels_for_each_run_come_from_the_file_of_its_split(tmp_path: Path) -> None:
    from tools import eval_score as es

    path = saved_sealed_run(tmp_path)
    assert es.golden_for_run(path) == SEALED_FILE


def test_sealed_runs_cannot_be_compared_to_choose_between_settings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from tools import eval_compare as compare

    path = saved_sealed_run(tmp_path)
    code = compare.main(["--a", str(path), "--b", str(path)])
    assert code == 2
    assert "sealed" in capsys.readouterr().err


def test_a_request_that_will_be_refused_does_not_open_the_sealed_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    opened: list[str] = []
    real = Path.read_text

    def spy(self: Path, *a: Any, **k: Any) -> str:
        opened.append(self.name)
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", spy)
    monkeypatch.setattr(er.ec, "git_state", lambda: GIT | {"dirty": True})
    assert er.main(["--split", "sealed", "--confirm-sealed-once", "--sealed-passes", "1"]) == 2
    assert "uncommitted" in capsys.readouterr().err
    assert SEALED_FILE.name not in opened
