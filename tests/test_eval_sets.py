"""The evaluation tools on a named golden set (D-100): the electrician's set runs as a locked
held-out set with its own ledger, against its own business and documents, and the scorer finds its
labels. No test reads the electrician's items: the runs below use tuned plumbing items filed
under the held-out name, as tests/test_eval_run.py does."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from citedesk.business import load_business
from citedesk.knowledge import FakeKB, KBResult
from citedesk.models import Source
from tests.test_eval_run import command, heldout_copy
from tests.test_eval_run import header as old_header
from tools import eval_common as ec
from tools import eval_run as er
from tools import eval_score
from tools.golden import SETS

REPO_ROOT = Path(__file__).resolve().parent.parent
ELECTRICIAN = load_business(REPO_ROOT / "universe-electrical/facts.json")
PLUMBER = load_business(REPO_ROOT / "universe/facts.json")


def test_each_set_has_its_labels_and_its_ledger() -> None:
    assert ec.golden_file_for("tuned") == ec.GOLDEN_FILE
    assert ec.golden_file_for("heldout", "fernhollow") == SETS["fernhollow"].golden_file
    assert ec.ledger_file_for("kestrel") == ec.LEDGER_FILE
    assert ec.ledger_file_for("fernhollow") == ec.FERNHOLLOW_LEDGER_FILE
    assert ec.FERNHOLLOW_LEDGER_FILE != ec.LEDGER_FILE
    assert "eval/fernhollow_ledger.json" in ec.IGNORED_FOR_DIRTY


def test_the_electricians_set_has_only_a_held_out_split() -> None:
    with pytest.raises(ValueError, match="holds only heldout items"):
        ec.golden_file_for("tuned", "fernhollow")
    assert er.set_problems("fernhollow", "tuned")
    assert er.set_problems("fernhollow", "heldout") == []
    assert er.set_problems("kestrel", "tuned") == []
    assert er.set_problems("nonesuch", "heldout")


def test_the_electricians_set_uses_the_electricians_fact_sheet() -> None:
    assert er.facts_for_set("fernhollow") == REPO_ROOT / "universe-electrical/facts.json"
    assert er.facts_for_set("kestrel") is None  # the settings decide, as before


def reply_from(text: str) -> FakeKB:
    source = Source(file="about.md", section="How to contact us", page=None, text=text)
    return FakeKB(lambda q: KBResult(answer="x", declined=False, sources=[source]))


def test_the_knowledge_base_must_serve_the_business_being_tested() -> None:
    electrician_docs = reply_from(f"Office phone: {ELECTRICIAN.phone}")
    plumber_docs = reply_from(f"Office phone: {PLUMBER.phone}")
    assert er.kb_serves(electrician_docs, ELECTRICIAN) is None
    problem = er.kb_serves(plumber_docs, ELECTRICIAN)
    assert problem is not None and "Fernhollow Electric" in problem
    assert er.kb_serves(reply_from(f"Office phone: {PLUMBER.phone}"), PLUMBER) is None


def test_a_knowledge_base_that_cannot_answer_is_a_problem() -> None:
    def broken(question: str) -> KBResult:
        raise OSError("down")

    assert er.kb_serves(FakeKB(broken), ELECTRICIAN) is not None


def test_a_run_of_the_electricians_set_says_so_in_its_header(tmp_path: Path) -> None:
    argv = ["--set", "fernhollow", "--split", "heldout", "--allow-heldout", "--heldout-passes", "1"]
    assert command(tmp_path, argv, heldout_copy()) == 0
    (run_file,) = (tmp_path / "runs").glob("*.run.json")
    header = json.loads(run_file.read_text("utf-8"))["header"]
    assert header["golden_set"] == "fernhollow"
    assert header["business"]["name"] == "Kestrel Hollow Plumbing"  # the business it was given
    assert run_file.name.startswith("eval-fernhollow-heldout-")


def test_a_kestrel_run_keeps_its_old_name_and_identity() -> None:
    stamp = datetime(2026, 11, 9, 12, 0, 0, tzinfo=UTC)
    assert er._run_id("tuned", "think-on", 1, stamp) == "eval-tuned-think-on-20261109-120000-p1"
    assert er._run_id("heldout", None, 1, stamp, "fernhollow").startswith("eval-fernhollow-")
    old = old_header()
    assert set(er.system_identity(old)) == {
        "code_tree", "universe_tree", "model", "prompt_versions", "settings", "rag",
        "split_sha256",
    }  # fmt: skip


def test_the_scorer_finds_the_labels_of_the_set_a_run_was_made_on(tmp_path: Path) -> None:
    run = tmp_path / "x.run.json"
    run.write_text(json.dumps({"header": {"split": "heldout", "golden_set": "fernhollow"}}))
    assert eval_score.golden_for_run(run) == SETS["fernhollow"].golden_file
    old = tmp_path / "y.run.json"
    old.write_text(json.dumps({"header": {"split": "heldout"}}))
    assert eval_score.golden_for_run(old) == ec.GOLDEN_FILE
