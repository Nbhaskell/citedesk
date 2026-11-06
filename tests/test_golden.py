import copy
import json
from pathlib import Path
from typing import Any

import pytest

from tools.golden import (
    GoldenFile,
    build_golden,
    derive_route,
    docs_sha256,
    load_docs,
    missing_fields,
    report,
    validate_data,
    validate_item,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = load_docs(REPO_ROOT / "universe/docs")


def make_item(**overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": "drain-price",
        "split": "tuned",
        "category": "routine_answerable",
        "channel": "web_form",
        "sender_name": "Alex Rivera",
        "sender_email": "alex.rivera@example.com",
        "subject": "Drain price",
        "body": "How much to clear a kitchen drain?",
        "labels": {
            "intents": ["pricing_question"],
            "primary_intent": "pricing_question",
            "urgency": "low",
            "fields": {
                "service_type": "drain_cleaning",
                "start_date": None,
                "property_type": None,
                "address_area": None,
            },
            "should_escalate": False,
            "expected_reason_codes": [],
            "expected_route": "draft_reply",
            "answerable_from_docs": True,
        },
        "evidence": [{"file": "pricing.md", "anchor": "$149 (starting price)"}],
        "notes": None,
    }
    labels_over = overrides.pop("labels", {})
    item.update(overrides)
    item["labels"] = {**item["labels"], **labels_over}
    return item


def problems(item: dict[str, Any]) -> list[str]:
    return validate_item(item, DOCS)


def labels(**kw: Any) -> dict[str, Any]:
    return {**make_item()["labels"], **kw}


# --- pure rules ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("intents", "fields", "expected"),
    [
        (["pricing_question"], {}, []),
        (
            ["booking_request"],
            {},
            ["service_type", "start_date", "property_type", "address_area"],
        ),
        (
            ["booking_request"],
            {
                "service_type": "drain_cleaning",
                "start_date": "2026-11-03",
                "property_type": "house",
                "address_area": "Millrace",
            },
            [],
        ),
        (["booking_change"], {"start_date": "2026-11-03"}, ["booking_reference"]),
        (["booking_change"], {"booking_reference": "KH-4471"}, ["start_date"]),
        (["cancellation"], {}, ["booking_reference"]),
        (["cancellation"], {"booking_reference": "KH-4471"}, []),
        (["availability_question"], {"service_type": "water_heater"}, ["start_date"]),
        (["booking_request", "pricing_question"], {"service_type": "inspection"}, None),
    ],
)
def test_missing_fields(
    intents: list[str], fields: dict[str, Any], expected: list[str] | None
) -> None:
    result = missing_fields(intents, fields)
    if expected is None:
        assert "start_date" in result and "service_type" not in result
    else:
        assert result == expected


def test_unknown_counts_as_missing() -> None:
    assert "service_type" in missing_fields(["availability_question"], {"service_type": "unknown"})


@pytest.mark.parametrize(
    ("intents", "primary", "reasons", "fields", "route"),
    [
        (["spam"], "spam", [], {}, "archive"),
        (["pricing_question"], "pricing_question", [], {}, "draft_reply"),
        (["health_or_safety"], "health_or_safety", ["HEALTH_SAFETY"], {}, "escalate"),
        (["complaint"], "complaint", ["COMPLAINT"], {}, "escalate"),
        (["booking_request"], "booking_request", [], {}, "request_details"),
        # An escalation reason beats missing details.
        (["booking_request"], "booking_request", ["POLICY_EXCEPTION_REQUEST"], {}, "escalate"),
        # NOT_IN_KNOWLEDGE_BASE only happens once the details are complete.
        (["pricing_question"], "pricing_question", ["NOT_IN_KNOWLEDGE_BASE"], {}, "escalate"),
        (["booking_request"], "booking_request", ["NOT_IN_KNOWLEDGE_BASE"], {}, "request_details"),
        # Spam mixed with a real intent is not archived.
        (["spam", "pricing_question"], "pricing_question", [], {}, "draft_reply"),
    ],
)
def test_derive_route(
    intents: list[str], primary: str, reasons: list[str], fields: dict[str, Any], route: str
) -> None:
    assert derive_route(intents, primary, reasons, fields) == route


# --- one valid item, then one failure at a time ----------------------------------------------


def test_a_valid_item_passes() -> None:
    assert problems(make_item()) == []


@pytest.mark.parametrize(
    ("overrides", "needle"),
    [
        ({"id": "Bad Id"}, "id"),
        ({"split": "dev"}, "split"),
        ({"category": "nonsense"}, "category"),
        ({"channel": "carrier_pigeon"}, "channel"),
        ({"body": ""}, "body"),
        ({"labels": {"intents": ["not_an_intent"]}}, "intent"),
        ({"labels": {"urgency": "asap"}}, "urgency"),
        ({"labels": {"expected_route": "yolo"}}, "route"),
        ({"labels": {"expected_reason_codes": ["VIBES"]}}, "reason"),
        ({"labels": {"intents": []}}, "intents"),
    ],
)
def test_schema_violations_are_reported(overrides: dict[str, Any], needle: str) -> None:
    result = problems(make_item(**overrides))
    assert result, f"expected a problem mentioning {needle!r}"
    assert any(needle in p.lower() for p in result), result


def test_extra_keys_are_rejected() -> None:
    assert problems({**make_item(), "surprise": 1})


def test_primary_intent_must_be_one_of_the_intents() -> None:
    result = problems(make_item(labels={"primary_intent": "complaint"}))
    assert any("primary_intent" in p for p in result)


def test_duplicate_intents_are_rejected() -> None:
    result = problems(make_item(labels={"intents": ["pricing_question", "pricing_question"]}))
    assert result


def test_expected_route_must_match_the_rules() -> None:
    result = problems(make_item(labels={"expected_route": "escalate"}))
    assert any("route" in p for p in result)


def test_should_escalate_must_match_the_route() -> None:
    result = problems(make_item(labels={"should_escalate": True}))
    assert any("should_escalate" in p for p in result)


def test_health_safety_intent_requires_the_reason_code() -> None:
    item = make_item(
        labels={
            "intents": ["health_or_safety"],
            "primary_intent": "health_or_safety",
            "should_escalate": True,
            "expected_route": "escalate",
            "expected_reason_codes": [],
            "answerable_from_docs": False,
        },
        evidence=[],
    )
    assert any("HEALTH_SAFETY" in p for p in problems(item))


def test_complaint_intent_requires_the_reason_code() -> None:
    item = make_item(
        labels={
            "intents": ["complaint"],
            "primary_intent": "complaint",
            "should_escalate": True,
            "expected_route": "escalate",
            "expected_reason_codes": ["REFUND_OR_DISPUTE"],
            "answerable_from_docs": False,
        },
        evidence=[],
    )
    assert any("COMPLAINT" in p for p in problems(item))


def test_a_commercial_property_requires_the_policy_exception_reason() -> None:
    commercial = {
        "service_type": "drain_cleaning",
        "start_date": None,
        "property_type": "commercial",
        "address_area": None,
    }
    item = make_item(labels={"fields": commercial})
    assert any("POLICY_EXCEPTION_REQUEST" in p for p in problems(item))
    escalated = make_item(
        labels={
            "fields": commercial,
            "should_escalate": True,
            "expected_route": "escalate",
            "expected_reason_codes": ["POLICY_EXCEPTION_REQUEST"],
        }
    )
    assert problems(escalated) == []


def test_not_in_kb_reason_is_rejected_when_details_are_missing() -> None:
    item = make_item(
        labels={
            "intents": ["availability_question"],
            "primary_intent": "availability_question",
            "expected_reason_codes": ["NOT_IN_KNOWLEDGE_BASE"],
            "should_escalate": False,
            "expected_route": "request_details",
            "answerable_from_docs": False,
        },
        evidence=[],
    )
    assert any("NOT_IN_KNOWLEDGE_BASE" in p for p in problems(item))


def test_answerable_items_need_evidence() -> None:
    assert any("evidence" in p for p in problems(make_item(evidence=[])))


def test_unanswerable_items_must_not_have_evidence() -> None:
    result = problems(make_item(labels={"answerable_from_docs": False}))
    assert any("evidence" in p for p in result)


def test_evidence_anchor_must_exist_in_the_named_document() -> None:
    bad = make_item(evidence=[{"file": "pricing.md", "anchor": "$999 (starting price)"}])
    assert any("anchor" in p for p in problems(bad))


def test_evidence_file_must_exist() -> None:
    bad = make_item(evidence=[{"file": "nope.md", "anchor": "x"}])
    assert any("nope.md" in p for p in problems(bad))


def test_evidence_matching_ignores_case_and_whitespace() -> None:
    ok = make_item(evidence=[{"file": "pricing.md", "anchor": "$149   (STARTING price)"}])
    assert problems(ok) == []


def test_dates_must_be_iso() -> None:
    bad = make_item(labels={"fields": {**make_item()["labels"]["fields"], "start_date": "12/3"}})
    assert any("start_date" in p for p in problems(bad))


def test_fields_must_have_the_core_keys() -> None:
    fields = make_item()["labels"]["fields"]
    del fields["address_area"]
    assert problems(make_item(labels={"fields": fields}))


def test_service_type_must_be_a_known_value() -> None:
    fields = {**make_item()["labels"]["fields"], "service_type": "plumbing"}
    assert problems(make_item(labels={"fields": fields}))


def test_real_looking_email_is_rejected() -> None:
    result = problems(make_item(sender_email="someone@" + "gmail.com"))
    assert any("example.com" in p for p in result)


def test_real_looking_email_in_body_is_rejected() -> None:
    result = problems(make_item(body="write me at someone@" + "gmail.com thanks"))
    assert any("example.com" in p for p in result)


@pytest.mark.parametrize(
    "phone", ["555-0134", "(555) 555-0187", "555.555.0150", "212-555-0134", "555 0123"]
)
def test_synthetic_phone_numbers_are_accepted(phone: str) -> None:
    assert problems(make_item(body=f"call me on {phone}")) == []


# Built from parts so this file never holds a real-looking number itself.
@pytest.mark.parametrize(
    "phone", ["415-" + "867-5309", "(312) " + "456-7890", "867-5309", "555-0234"]
)
def test_other_phone_numbers_are_rejected(phone: str) -> None:
    result = problems(make_item(body=f"call me on {phone}"))
    assert any("phone" in p.lower() for p in result), phone


# --- whole-file rules ------------------------------------------------------------------------


def make_file(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "header": {
            "name": "citedesk_v1",
            "version": 1,
            "reference_date": "2026-10-28",
            "written_by": "an AI model; not blind to the fact sheet",
            "docs_sha256": docs_sha256(DOCS),
            "counts": {"items": len(items)},
        },
        "items": items,
    }


def test_a_valid_file_passes() -> None:
    assert validate_data(make_file([make_item()]), DOCS) == []


def test_duplicate_ids_are_reported() -> None:
    result = validate_data(make_file([make_item(), make_item()]), DOCS)
    assert any("duplicate" in p.lower() for p in result)


def test_stale_document_hash_is_reported() -> None:
    data = make_file([make_item()])
    data["header"]["docs_sha256"] = "0" * 64
    assert any("documents" in p.lower() for p in validate_data(data, DOCS))


def test_item_problems_carry_the_item_id() -> None:
    bad = make_item(labels={"expected_route": "escalate"})
    result = validate_data(make_file([bad]), DOCS)
    assert any(p.startswith("drain-price:") for p in result)


def test_report_counts_intents_and_categories() -> None:
    other = make_item(id="second", category="vague_missing_details")
    text = report(make_file([make_item(), other]))
    assert "pricing_question" in text and "routine_answerable" in text
    assert "vague_missing_details" in text and "2 items" in text


def test_build_merges_source_files_sorted_by_id(tmp_path: Path) -> None:
    (tmp_path / "b.json").write_text(json.dumps([make_item(id="zebra")]), "utf-8")
    (tmp_path / "a.json").write_text(json.dumps([make_item(id="apple")]), "utf-8")
    data = build_golden(tmp_path, DOCS, name="citedesk_v1", version=1, written_by="x")
    assert [i["id"] for i in data["items"]] == ["apple", "zebra"]
    assert data["header"]["counts"]["items"] == 2
    assert data["header"]["docs_sha256"] == docs_sha256(DOCS)


def test_build_does_not_mutate_inputs(tmp_path: Path) -> None:
    original = make_item()
    snapshot = copy.deepcopy(original)
    (tmp_path / "a.json").write_text(json.dumps([original]), "utf-8")
    build_golden(tmp_path, DOCS, name="n", version=1, written_by="x")
    assert original == snapshot


# --- the committed files ---------------------------------------------------------------------


def test_json_schema_file_is_current() -> None:
    committed = json.loads((REPO_ROOT / "eval/golden/golden.schema.json").read_text("utf-8"))
    assert committed == GoldenFile.model_json_schema()


def test_committed_golden_set_is_valid_and_current() -> None:
    path = REPO_ROOT / "eval/golden/citedesk_v1.json"
    data = json.loads(path.read_text("utf-8"))
    assert validate_data(data, DOCS) == []
    rebuilt = build_golden(
        REPO_ROOT / "eval/golden/src",
        DOCS,
        name=data["header"]["name"],
        version=data["header"]["version"],
        written_by=data["header"]["written_by"],
    )
    assert rebuilt == data, "run: python -m tools.golden build"
