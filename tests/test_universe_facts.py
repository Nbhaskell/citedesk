import json
import re
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def facts() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((REPO_ROOT / "universe/facts.json").read_text("utf-8"))
    return data


def schema_enum(name: str) -> set[str]:
    """Read an enumeration row from the table in docs/BACKEND_SCHEMA.md section 1."""
    for line in (REPO_ROOT / "docs/BACKEND_SCHEMA.md").read_text("utf-8").splitlines():
        if line.startswith(f"| `{name}` |"):
            cells = line.split("|")
            return set(re.findall(r"`([^`]+)`", cells[2]))
    raise AssertionError(f"enum {name} not found in BACKEND_SCHEMA.md")


def walk(node: Any) -> list[Any]:
    out = [node]
    if isinstance(node, dict):
        for child in node.values():
            out += walk(child)
    elif isinstance(node, list):
        for child in node:
            out += walk(child)
    return out


def test_facts_are_marked_synthetic(facts: dict[str, Any]) -> None:
    assert facts["synthetic"] is True
    assert "SYNTHETIC" in facts["_comment"]


def test_every_service_type_in_facts_is_in_the_schema_enum(facts: dict[str, Any]) -> None:
    used = {n["service_type"] for n in walk(facts) if isinstance(n, dict) and "service_type" in n}
    assert used, "no service_type values found in facts.json"
    assert used <= schema_enum("service_type")


def test_every_offered_service_is_mapped_and_none_is_also_excluded(facts: dict[str, Any]) -> None:
    offered = facts["services_offered"]
    assert {s["service_type"] for s in offered} <= schema_enum("service_type")
    not_offered = " ".join(facts["policies"]["not_offered"]).lower()
    for service in offered:
        for word in re.findall(r"[a-z]{5,}", service["name"].lower()):
            assert word not in not_offered, f"{service['name']!r} clashes with not_offered"


def test_phone_numbers_are_in_the_555_01xx_range(facts: dict[str, Any]) -> None:
    phones = [facts["business"]["phone"], facts["business"]["emergency_phone"]]
    assert all(re.fullmatch(r"555-01\d\d", p) for p in phones)


def test_emails_are_at_example_com(facts: dict[str, Any]) -> None:
    text = json.dumps(facts)
    emails = re.findall(r"[\w.+-]+@[\w.-]+", text)
    assert emails
    assert all(e.endswith("@example.com") for e in emails)
