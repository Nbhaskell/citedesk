import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest

from tools.check_consistency import check
from tools.generate_kb_docs import render_docs

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_FILES = {
    "about.md",
    "emergencies.md",
    "faq.md",
    "hours.md",
    "policies.md",
    "pricing.md",
    "service-area.md",
    "services.md",
}


@pytest.fixture(scope="module")
def facts() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((REPO_ROOT / "universe/facts.json").read_text("utf-8"))
    return data


@pytest.fixture
def docs(facts: dict[str, Any]) -> dict[str, str]:
    return render_docs(facts)


# --- the generator ---------------------------------------------------------------------------


def test_generator_makes_the_expected_files(docs: dict[str, str]) -> None:
    assert set(docs) == EXPECTED_FILES


def test_generation_is_deterministic(facts: dict[str, Any]) -> None:
    assert render_docs(facts) == render_docs(copy.deepcopy(facts))


def test_every_doc_has_one_title_and_several_sections(docs: dict[str, str]) -> None:
    for name, text in docs.items():
        titles = re.findall(r"^# .+$", text, flags=re.MULTILINE)
        sections = re.findall(r"^## .+$", text, flags=re.MULTILINE)
        assert len(titles) == 1, name
        assert text.startswith("# "), name
        assert len(sections) >= 2, name


def test_docs_have_no_numbered_lists_or_html(docs: dict[str, str]) -> None:
    for name, text in docs.items():
        assert not re.search(r"^\d+\.\s", text, flags=re.MULTILINE), name
        assert "<" not in text, name


def test_pricing_headings_match_the_schema_example(docs: dict[str, str]) -> None:
    # docs/BACKEND_SCHEMA.md shows the source section "Pricing > Drain cleaning".
    assert re.search(r"^# Pricing$", docs["pricing.md"], flags=re.MULTILINE)
    assert re.search(r"^## Drain cleaning$", docs["pricing.md"], flags=re.MULTILINE)


def test_each_not_offered_item_has_its_own_short_section(
    facts: dict[str, Any], docs: dict[str, str]
) -> None:
    # One topic per section keeps each exclusion retrievable on its own. A single bare list of
    # nine unrelated items was never retrieved for any of the nine matching questions.
    policies = docs["policies.md"]
    for item in facts["policies"]["not_offered"]:
        match = re.search(rf"^## {re.escape(item)}\n\n([^\n]+)", policies, re.MULTILINE)
        assert match, f"no section for {item!r}"
        body = match.group(1)
        assert re.search(r"\bnot\b", body), f"section for {item!r} is not a clear refusal: {body!r}"
        assert not body.startswith("-"), f"section for {item!r} is a bare list item"


def test_committed_docs_are_what_the_generator_produces(docs: dict[str, str]) -> None:
    on_disk = {p.name: p.read_text("utf-8") for p in (REPO_ROOT / "universe/docs").glob("*.md")}
    assert on_disk == docs, "run: python -m tools.generate_kb_docs"


def test_manifest_matches_the_files_on_disk() -> None:
    import hashlib

    manifest = json.loads((REPO_ROOT / "universe/manifest.json").read_text("utf-8"))
    facts_hash = hashlib.sha256((REPO_ROOT / "universe/facts.json").read_bytes()).hexdigest()
    assert manifest["facts_sha256"] == facts_hash
    for name, digest in manifest["docs"].items():
        file_bytes = (REPO_ROOT / "universe/docs" / name).read_bytes()
        assert hashlib.sha256(file_bytes).hexdigest() == digest


# --- the checker: passes on good documents ----------------------------------------------------


def test_checker_passes_on_generated_docs(facts: dict[str, Any], docs: dict[str, str]) -> None:
    assert check(facts, docs) == []


# --- the checker: known-bad documents must be caught -----------------------------------------


def broken(docs: dict[str, str], name: str, old: str, new: str) -> dict[str, str]:
    assert old in docs[name], f"test setup: {old!r} not in {name}"
    return {**docs, name: docs[name].replace(old, new, 1)}


def test_catches_a_wrong_price(facts: dict[str, Any], docs: dict[str, str]) -> None:
    bad = broken(docs, "pricing.md", "$149", "$159")
    problems = check(facts, bad)
    assert any("$159" in p for p in problems)


def test_catches_a_price_that_is_missing(facts: dict[str, Any], docs: dict[str, str]) -> None:
    bad = {k: v.replace("$329", "an amount") for k, v in docs.items()}
    problems = check(facts, bad)
    assert any("$329" in p and "missing" in p.lower() for p in problems)


def test_catches_an_invented_total(facts: dict[str, Any], docs: dict[str, str]) -> None:
    bad = {**docs, "faq.md": docs["faq.md"] + "\nA drain visit usually totals $238.\n"}
    assert any("$238" in p for p in check(facts, bad))


def test_catches_a_wrong_time(facts: dict[str, Any], docs: dict[str, str]) -> None:
    bad = broken(docs, "hours.md", "7:30 am", "7:45 am")
    assert any("7:45" in p for p in check(facts, bad))


def test_catches_a_wrong_date(facts: dict[str, Any], docs: dict[str, str]) -> None:
    bad = broken(docs, "hours.md", "November 26, 2026", "November 27, 2026")
    problems = check(facts, bad)
    assert any("November 27, 2026" in p for p in problems)
    assert any("2026-11-26" in p and "missing" in p.lower() for p in problems)


def test_catches_a_wrong_percentage(facts: dict[str, Any], docs: dict[str, str]) -> None:
    bad = broken(docs, "pricing.md", "7%", "8%")
    assert any("8%" in p for p in check(facts, bad))


def test_catches_an_unknown_phone_number(facts: dict[str, Any], docs: dict[str, str]) -> None:
    bad = {**docs, "about.md": docs["about.md"] + "\nCall 555-0199 for sales.\n"}
    assert any("555-0199" in p for p in check(facts, bad))


def test_catches_a_real_looking_email(facts: dict[str, Any], docs: dict[str, str]) -> None:
    bad = {**docs, "about.md": docs["about.md"] + "\nWrite to help@gmail.com\n"}
    assert any("help@gmail.com" in p for p in check(facts, bad))


def test_catches_an_invented_number_of_hours(facts: dict[str, Any], docs: dict[str, str]) -> None:
    bad = broken(docs, "policies.md", "24 hours", "48 hours")
    assert any("48" in p for p in check(facts, bad))


def test_catches_a_dropped_not_offered_item(facts: dict[str, Any], docs: dict[str, str]) -> None:
    without_item = re.sub("roof leaks", "", docs["policies.md"], flags=re.IGNORECASE)
    bad = {**docs, "policies.md": without_item}
    assert any("Roof leaks" in p for p in check(facts, bad))


def test_catches_a_service_missing_from_the_services_doc(
    facts: dict[str, Any], docs: dict[str, str]
) -> None:
    bad = {**docs, "services.md": docs["services.md"].replace("Slab leak repair", "")}
    assert any("Slab leak repair" in p for p in check(facts, bad))


def test_checker_notices_when_facts_change_but_docs_do_not(
    facts: dict[str, Any], docs: dict[str, str]
) -> None:
    changed = copy.deepcopy(facts)
    changed["pricing"]["labour"]["price_per_hour"] = 120
    problems = check(changed, docs)
    assert any("$115" in p for p in problems)
    assert any("$120" in p for p in problems)
