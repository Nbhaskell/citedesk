"""The documents of the invented electrical business (D-098): generated, consistent, current, and
free of plumbing. The plumbing documents are covered by tests/test_kb_docs.py."""

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest

from citedesk.models import ServiceType
from citedesk.trade import ELECTRICAL, load_trade
from tools.check_consistency import check
from tools.generate_kb_docs import render_docs
from tools.kb_electrical import NOT_OFFERED_SENTENCES, SERVICE_DESCRIPTIONS

REPO_ROOT = Path(__file__).resolve().parent.parent
UNIVERSE = REPO_ROOT / "universe-electrical"


@pytest.fixture(scope="module")
def facts() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((UNIVERSE / "facts.json").read_text("utf-8"))
    return data


@pytest.fixture
def docs(facts: dict[str, Any]) -> dict[str, str]:
    return render_docs(facts)


def test_the_fact_sheet_is_the_electrical_trade() -> None:
    assert load_trade(UNIVERSE / "facts.json") is ELECTRICAL


def test_the_fact_sheet_is_labelled_synthetic_with_safe_contacts(facts: dict[str, Any]) -> None:
    assert facts["synthetic"] is True
    business = facts["business"]
    for phone in (business["phone"], business["emergency_phone"]):
        assert re.fullmatch(r"555-01\d\d", phone)
    assert business["email"].endswith("@example.com")


def test_every_service_uses_an_electrical_service_type(facts: dict[str, Any]) -> None:
    allowed = {member.value for member in ELECTRICAL.service_types}
    used = {s["service_type"] for s in facts["services_offered"]}
    used |= {j["service_type"] for j in facts["pricing"]["flat_price_jobs"]}
    assert used <= allowed
    assert ServiceType.panel_upgrade.value in used


def test_every_service_and_exclusion_has_its_wording(facts: dict[str, Any]) -> None:
    assert {s["name"] for s in facts["services_offered"]} == set(SERVICE_DESCRIPTIONS)
    assert set(facts["policies"]["not_offered"]) == set(NOT_OFFERED_SENTENCES)


def test_the_generated_documents_agree_with_the_fact_sheet(
    facts: dict[str, Any], docs: dict[str, str]
) -> None:
    assert check(facts, docs) == []


def test_the_committed_documents_are_what_the_generator_produces(docs: dict[str, str]) -> None:
    on_disk = {p.name: p.read_text("utf-8") for p in (UNIVERSE / "docs").glob("*.md")}
    assert on_disk == docs


def test_the_manifest_matches_the_files(docs: dict[str, str]) -> None:
    manifest = json.loads((UNIVERSE / "manifest.json").read_text("utf-8"))
    for name in docs:
        data = (UNIVERSE / "docs" / name).read_bytes()
        assert manifest["docs"][name] == hashlib.sha256(data).hexdigest()


def test_the_documents_hold_no_plumbing_offer(docs: dict[str, str]) -> None:
    # "plumbing" may appear only to say the business does not do it, or in a question a customer
    # asks, whose answer is no
    for name, text in docs.items():
        for line in text.splitlines():
            if re.search(r"plumb", line, re.IGNORECASE):
                allowed = r"\b(?:not|no)\b|^## Plumbing$|^- Plumbing$|^## .*\?$"
                assert re.search(allowed, line, re.IGNORECASE), (name, line)
