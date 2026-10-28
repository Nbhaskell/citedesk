"""The Phase 5 reading run, with scripted fakes."""

import json
from pathlib import Path
from typing import Any

import pytest

from citedesk.business import Business
from citedesk.config import Settings
from citedesk.knowledge import FakeKB
from citedesk.providers import FakeLLM
from citedesk.screening import screen
from tests.helpers import perfect_reply
from tools import run_pipeline as rp
from tools.score_understanding import make_run

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN = json.loads((REPO_ROOT / "eval/golden/citedesk_v1.json").read_text("utf-8"))
TUNED = [i for i in GOLDEN["items"] if i["split"] == "tuned"]
BUSINESS = Business("Kestrel Hollow Plumbing", "555-0171", "555-0172", "kestrelhollow@example.com")
DRAFT = {
    "subject": "Re: Question",
    "body": "Hi,\n\nDrain cleaning starts at $149.\n\nKind regards,\nKestrel Hollow Plumbing",
    "claims": [{"text": "starts at $149", "source_index": 0}],
}


@pytest.fixture(scope="module")
def run() -> dict[str, Any]:
    by_body = {
        screen(i.get("subject"), i["body"], spam_threshold=0.8).body.strip(): i for i in TUNED
    }

    def model(call: Any) -> dict[str, Any]:
        if "claims" in call.schema["properties"]:
            return DRAFT
        return perfect_reply(next(i for b, i in by_body.items() if b in call.user))

    return make_run(
        TUNED[:40],
        Settings(_env_file=None),
        FakeLLM(model),
        split="tuned",
        reference_date="2026-10-28",
        kb=FakeKB(lambda q: FakeKB.answered("$149", ["pricing.md"], text="Drain cleaning: $149")),
        business=BUSINESS,
        with_drafts=True,
    )


def test_drafts_and_checks_are_kept_when_asked(run: dict[str, Any]) -> None:
    drafted = [r for r in run["items"] if r["draft"]]
    assert drafted
    first = drafted[0]
    assert first["draft"]["status"] in ("ready", "blocked") and first["checks"]
    assert (
        {"question", "declined", "answer", "sources"} <= set(first["retrievals"][0])
        if first["retrievals"]
        else True
    )


def test_the_summary_counts_statuses_and_checks(run: dict[str, Any]) -> None:
    text = rp.summarise(run)
    for needle in (
        "status",
        "drafts",
        "FIGURES_GROUNDED",
        "ungrounded figures",
        "escalated by a check",
    ):
        assert needle in text


def test_the_reading_sheet_holds_the_asked_number_beside_what_each_answers(
    run: dict[str, Any],
) -> None:
    items = {i["id"]: i for i in GOLDEN["items"]}
    sheet = rp.reading_sheet(run, items, 5)
    assert sheet.count("\n## ") == 5
    assert "SYNTHETIC DATA" in sheet and "**Customer**" in sheet and "**Draft**" in sheet
    assert "Notes:" in sheet


def test_a_sheet_bigger_than_the_drafts_holds_them_all(run: dict[str, Any]) -> None:
    items = {i["id"]: i for i in GOLDEN["items"]}
    drafted = sum(1 for r in run["items"] if r["draft"])
    assert rp.reading_sheet(run, items, 500).count("\n## ") == drafted


def test_the_held_out_split_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    assert rp.main(["--split", "heldout"]) == 2
    assert "Phase 7" in capsys.readouterr().err


def test_the_sheet_shows_the_passage_text_beside_its_claim_number(run: dict[str, Any]) -> None:
    items = {i["id"]: i for i in GOLDEN["items"]}
    sheet = rp.reading_sheet(run, items, 3)
    assert "**Passages the draft was written from**" in sheet
    assert "- [0] pricing.md" in sheet and "Drain cleaning: $149" in sheet


def test_a_sheet_can_be_rewritten_from_a_saved_run(
    run: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    saved = tmp_path / "x.drafts.json"
    saved.write_text(json.dumps(run), encoding="utf-8")
    assert rp.main(["--sheet-from", str(saved), "--sheet", "2"]) == 0
    written = (tmp_path / "x.sheet.md").read_text("utf-8")
    assert written.count("\n## ") == 2
