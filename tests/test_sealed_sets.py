"""The second sealed sets (D-104): one for the invented plumber, one for the invented electrician.
Each is kept out of git, sealed by a committed hash, and run once under its own ledger. No test
reads any sealed item: the files used here are invented in the test."""

import json
import subprocess
from pathlib import Path

import pytest

from tools import eval_common as ec
from tools import eval_run as er
from tools import golden
from tools.golden import SETS

NEW = ("kestrel-2", "fernhollow-2")


def test_the_new_sets_are_sealed_and_kept_out_of_git() -> None:
    for key in NEW:
        target = SETS[key]
        assert target.sealed and target.splits == ("sealed",)
        assert target.golden_file.is_relative_to(golden.REPO_ROOT / "data")
        assert target.src_dir.is_relative_to(golden.REPO_ROOT / "data")
        ignored = subprocess.run(  # noqa: S603 (a fixed git command on the repository's own path)
            ["git", "check-ignore", "-q", str(target.golden_file)],  # noqa: S607
            cwd=golden.REPO_ROOT,
            check=False,
        )
        assert ignored.returncode == 0, f"{key} would be tracked by git"
        assert target.hash_file is not None
        assert not target.hash_file.is_relative_to(golden.REPO_ROOT / "data")
    assert not SETS["kestrel"].sealed and not SETS["fernhollow"].sealed


def test_each_set_has_its_own_files_hash_and_ledger() -> None:
    files = {golden.SEALED_FILE} | {SETS[k].golden_file for k in NEW}
    hashes = {golden.SEALED_HASH_FILE} | {SETS[k].hash_file for k in NEW}
    ledgers = {ec.sealed_ledger_file_for(k) for k in ("kestrel", *NEW)}
    assert len(files) == len(hashes) == len(ledgers) == 3
    assert ec.LEDGER_FILE not in ledgers and ec.FERNHOLLOW_LEDGER_FILE not in ledgers
    for key in NEW:
        ledger = ec.sealed_ledger_file_for(key)
        assert ledger is not None
        assert str(ledger.relative_to(golden.REPO_ROOT)).replace("\\", "/") in ec.IGNORED_FOR_DIRTY


def test_the_trades_and_documents_match_the_businesses() -> None:
    assert SETS["kestrel-2"].trade.key == "plumbing"
    assert SETS["kestrel-2"].docs_dir == golden.DOCS_DIR
    assert SETS["fernhollow-2"].trade.key == "electrical"
    assert SETS["fernhollow-2"].docs_dir == golden.REPO_ROOT / "universe-electrical/docs"
    assert er.facts_for_set("fernhollow-2") == golden.REPO_ROOT / "universe-electrical/facts.json"
    assert er.facts_for_set("kestrel-2") == golden.REPO_ROOT / "universe/facts.json"


def test_a_new_set_runs_only_as_a_sealed_split() -> None:
    for key in NEW:
        assert er.set_problems(key, "sealed") == []
        assert er.set_problems(key, "heldout")
        assert er.set_problems(key, "tuned")
        assert ec.golden_file_for("sealed", key) == SETS[key].golden_file
        with pytest.raises(ValueError, match="holds only sealed items"):
            ec.golden_file_for("heldout", key)
    assert ec.sealed_files_for("kestrel") == (golden.SEALED_FILE, golden.SEALED_HASH_FILE)
    assert ec.sealed_files_for("fernhollow") is None


def test_the_refusal_names_the_sets_own_hash_file() -> None:
    problems = er.ledger_mod.sealed_problems(
        split="sealed",
        confirmed=True,
        limit=None,
        dirty=False,
        git_known=True,
        hash_matches=False,
        hash_name="fernhollow_sealed.sha256",
    )
    assert any("fernhollow_sealed.sha256" in p for p in problems)


def sealed_set(tmp_path: Path, key: str) -> golden.GoldenSet:
    """The named set with its files moved into a temporary folder."""
    base = SETS[key]
    return golden.GoldenSet(
        key=base.key,
        name=base.name,
        src_dir=tmp_path / "src",
        golden_file=tmp_path / "built.json",
        docs_dir=base.docs_dir,
        written_by=base.written_by,
        splits=base.splits,
        trade=base.trade,
        hash_file=tmp_path / "set.sha256",
    )


def test_seal_and_verify_a_named_set(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = sealed_set(tmp_path, "kestrel-2")
    target.golden_file.write_text(json.dumps({"header": {}, "items": []}), encoding="utf-8")
    assert golden.cmd_seal_named("seal", target, target.key) == 0
    assert golden.cmd_seal_named("verify-sealed", target, target.key) == 0
    with pytest.raises(FileExistsError):
        golden.cmd_seal_named("seal", target, target.key)
    target.golden_file.write_text("changed", encoding="utf-8")
    assert golden.cmd_seal_named("verify-sealed", target, target.key) == 1
    assert golden.cmd_seal_named("seal", SETS["fernhollow"], "fernhollow") == 2
    assert "MISMATCH" in capsys.readouterr().out


def test_a_sealed_set_is_not_rebuilt_once_sealed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = sealed_set(tmp_path, "fernhollow-2")
    assert target.hash_file is not None
    target.hash_file.write_text("0" * 64 + "\n", encoding="utf-8")
    assert golden.cmd_build(target) == 1
    assert "is sealed" in capsys.readouterr().out
    assert not target.golden_file.exists()
