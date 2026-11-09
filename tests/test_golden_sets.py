"""Named golden sets (D-099): the plumbing set as before, and a set for the invented electrician
that takes only held-out items and only the electrical service types. Fixtures are invented."""

import json
from pathlib import Path
from typing import Any

import pytest

from citedesk.trade import ELECTRICAL, PLUMBING
from tools import golden

ELECTRICAL_DOCS = {"faq.md": "## Do you charge to come out?\n\nYes. The call-out fee is $95.\n"}


def item(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "price-call-out",
        "split": "heldout",
        "category": "routine_answerable",
        "channel": "email",
        "sender_name": "Pat Example",
        "subject": "Call-out fee",
        "body": "How much do you charge to come out?",
        "labels": {
            "intents": ["pricing_question"],
            "primary_intent": "pricing_question",
            "urgency": "low",
            "fields": {
                "service_type": None,
                "start_date": None,
                "property_type": None,
                "address_area": None,
            },  # fmt: skip
            "should_escalate": False,
            "expected_reason_codes": [],
            "expected_route": "draft_reply",
            "answerable_from_docs": True,
        },
        "evidence": [{"file": "faq.md", "anchor": "The call-out fee is $95"}],
    }
    return base | over


def with_service(service: str) -> dict[str, Any]:
    raw = item()
    raw["labels"]["fields"]["service_type"] = service
    return raw


def test_the_known_sets_point_at_their_own_folders_and_trades() -> None:
    kestrel, fernhollow = golden.SETS["kestrel"], golden.SETS["fernhollow"]
    assert kestrel.golden_file == golden.GOLDEN_FILE and kestrel.trade is PLUMBING
    assert kestrel.splits == golden.MAIN_SPLITS
    assert fernhollow.docs_dir.parts[-2:] == ("universe-electrical", "docs")
    assert fernhollow.trade is ELECTRICAL
    assert fernhollow.splits == ("heldout",)


def test_an_electrical_item_validates_against_electrical_documents() -> None:
    assert golden.validate_item(item(), ELECTRICAL_DOCS, ELECTRICAL) == []


def test_a_service_type_from_another_trade_is_refused() -> None:
    problems = golden.validate_item(with_service("drain_cleaning"), ELECTRICAL_DOCS, ELECTRICAL)
    assert any("not a service type of the electrical trade" in p for p in problems)
    assert golden.validate_item(with_service("panel_upgrade"), ELECTRICAL_DOCS, ELECTRICAL) == []
    plumbing = golden.validate_item(with_service("panel_upgrade"), ELECTRICAL_DOCS, PLUMBING)
    assert any("not a service type of the plumbing trade" in p for p in problems + plumbing)


def test_the_electrical_set_takes_only_held_out_items() -> None:
    fernhollow = golden.SETS["fernhollow"]
    data = golden.build_golden_items([item(split="tuned")], ELECTRICAL_DOCS, fernhollow)
    problems = golden.validate_data(
        data, ELECTRICAL_DOCS, allowed_splits=fernhollow.splits, trade=fernhollow.trade
    )
    assert any("split 'tuned' is not allowed" in p for p in problems)


def test_build_and_validate_a_named_set_from_its_own_folders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    docs_dir, src_dir = tmp_path / "docs", tmp_path / "src"
    docs_dir.mkdir()
    src_dir.mkdir()
    (docs_dir / "faq.md").write_text(ELECTRICAL_DOCS["faq.md"], encoding="utf-8")
    (src_dir / "items.json").write_text(json.dumps([item()]), encoding="utf-8")
    target = golden.GoldenSet(
        key="test",
        name="test_v1",
        src_dir=src_dir,
        golden_file=tmp_path / "test_v1.json",
        docs_dir=docs_dir,
        written_by="invented for a test",
        splits=("heldout",),
        trade=ELECTRICAL,
    )
    monkeypatch.setitem(golden.SETS, "test", target)
    assert golden.main(["golden", "build", "--set", "test"]) == 0
    assert golden.main(["golden", "validate", "--set", "test"]) == 0
    built = json.loads(target.golden_file.read_text("utf-8"))
    assert built["header"]["name"] == "test_v1" and len(built["items"]) == 1


def test_an_unknown_set_is_refused() -> None:
    assert golden.main(["golden", "validate", "--set", "nonesuch"]) == 2
