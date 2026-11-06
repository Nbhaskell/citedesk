import enum
import re
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from citedesk import models
from citedesk.db import MIGRATIONS_DIR, connect, migrate

REPO_ROOT = Path(__file__).resolve().parent.parent

# Section 1 of BACKEND_SCHEMA.md: row name in the table to enum class in models.py.
DOC_ENUMS = {
    "channel": models.Channel,
    "intent": models.Intent,
    "urgency": models.Urgency,
    "sentiment": models.Sentiment,
    "confidence": models.Confidence,
    "route": models.Route,
    "inquiry_status": models.InquiryStatus,
    "reason_code": models.ReasonCode,
    "check_code": models.CheckCode,
    "draft_kind": models.DraftKind,
    "draft_status": models.DraftStatus,
    "decision": models.Decision,
    "service_type": models.ServiceType,
    "property_type": models.PropertyType,
    "stage": models.Stage,
}

# Every CHECK (column IN (...)) in the database: (table, column) to enum class.
CHECK_ENUMS = {
    ("inquiries", "channel"): models.Channel,
    ("inquiries", "status"): models.InquiryStatus,
    ("inquiries", "route"): models.Route,
    ("inquiries", "urgency"): models.Urgency,
    ("screenings", "result"): models.ScreeningResult,
    ("classifications", "primary_confidence"): models.Confidence,
    ("classifications", "urgency"): models.Urgency,
    ("classifications", "sentiment"): models.Sentiment,
    ("escalations", "reason_code"): models.ReasonCode,
    ("escalations", "source"): models.EscalationSource,
    ("drafts", "kind"): models.DraftKind,
    ("drafts", "status"): models.DraftStatus,
    ("draft_checks", "check_code"): models.CheckCode,
    ("reviews", "decision"): models.Decision,
    ("exports", "method"): models.ExportMethod,
}


def doc_enum_rows() -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    text = (REPO_ROOT / "docs/BACKEND_SCHEMA.md").read_text("utf-8")
    section = text.split("## 1. Enumerations", 1)[1].split("## 2.", 1)[0]
    for line in section.splitlines():
        match = re.match(r"^\| `(\w+)`[^|]*\|(.*)\|\s*$", line)
        if match:
            rows[match.group(1)] = re.findall(r"`([^`]+)`", match.group(2))
    return rows


def check_constraints_in_database(
    directory: Path | None = None,
) -> dict[tuple[str, str], list[str]]:
    conn = connect(":memory:")
    migrate(conn, directory or MIGRATIONS_DIR)
    found: dict[tuple[str, str], list[str]] = {}
    for row in conn.execute("SELECT name, sql FROM sqlite_master WHERE type = 'table'"):
        for column, values in re.findall(
            r"CHECK\s*\(\s*(\w+)\s+IN\s*\(([^)]*)\)\s*\)", row["sql"], flags=re.DOTALL
        ):
            found[(row["name"], column)] = re.findall(r"'([^']*)'", values)
    conn.close()
    return found


def all_enum_classes() -> list[type[enum.Enum]]:
    return [
        obj
        for obj in vars(models).values()
        if isinstance(obj, type)
        and issubclass(obj, enum.Enum)
        and obj.__module__ == models.__name__
    ]


# --- enums match the schema document ---------------------------------------------------------


@pytest.mark.parametrize("name", sorted(DOC_ENUMS))
def test_enum_matches_the_schema_document(name: str) -> None:
    doc = doc_enum_rows()
    assert name in doc, f"{name} not found in section 1 of BACKEND_SCHEMA.md"
    assert [m.value for m in DOC_ENUMS[name]] == doc[name]


def test_every_enumeration_row_in_the_document_has_a_class() -> None:
    assert set(doc_enum_rows()) == set(DOC_ENUMS)


# --- enums match the database CHECK constraints ----------------------------------------------


def test_every_check_constraint_in_the_database_is_covered() -> None:
    assert set(check_constraints_in_database()) == set(CHECK_ENUMS)


@pytest.mark.parametrize(("table", "column"), sorted(CHECK_ENUMS))
def test_enum_values_equal_the_database_check_values(table: str, column: str) -> None:
    in_db = check_constraints_in_database()[(table, column)]
    in_code = [m.value for m in CHECK_ENUMS[(table, column)]]
    assert sorted(in_code) == sorted(in_db), f"{table}.{column}: code and database disagree"


def test_the_comparison_would_catch_drift(tmp_path: Path) -> None:
    """Known-bad check: a status added to the database only must show up as a mismatch."""
    sql = (REPO_ROOT / "db/migrations/0001_init.sql").read_text("utf-8")
    assert "'archived','failed')" in sql
    doctored = sql.replace("'archived','failed')", "'archived','failed','zombie')")
    (tmp_path / "0001_init.sql").write_text(doctored, "utf-8")
    in_db = check_constraints_in_database(tmp_path)[("inquiries", "status")]
    in_code = [m.value for m in models.InquiryStatus]
    assert "zombie" in in_db
    assert sorted(in_code) != sorted(in_db)


def test_database_accepts_every_enum_value_and_rejects_others() -> None:
    conn = connect(":memory:")
    migrate(conn)
    for status in models.InquiryStatus:
        conn.execute(
            "INSERT INTO inquiries (channel, received_at, body, status, created_at, updated_at) "
            "VALUES ('web_form', 'x', 'b', ?, 'x', 'x')",
            (status.value,),
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO inquiries (channel, received_at, body, status, created_at, updated_at) "
            "VALUES ('web_form', 'x', 'b', 'nonsense', 'x', 'x')"
        )


def test_audit_event_types_match_the_documented_list() -> None:
    sql = (REPO_ROOT / "db/migrations/0001_init.sql").read_text("utf-8")
    line = next(ln for ln in sql.splitlines() if ln.strip().startswith("event_type"))
    documented = re.split(r",\s*", line.split("--", 1)[1].strip())
    assert [m.value for m in models.AuditEventType] == documented


def test_no_enum_is_unaccounted_for() -> None:
    known = set(DOC_ENUMS.values()) | set(CHECK_ENUMS.values()) | {models.AuditEventType}
    assert set(all_enum_classes()) == known


# --- enum behaviour --------------------------------------------------------------------------


def test_enums_are_strings_with_exact_values() -> None:
    assert models.Intent("pricing_question") is models.Intent.pricing_question
    assert models.ReasonCode.HEALTH_SAFETY == "HEALTH_SAFETY"
    assert str(models.Route.escalate) == "escalate"
    with pytest.raises(ValueError, match="nonsense"):
        models.Intent("nonsense")


# --- JSON shapes -----------------------------------------------------------------------------

FIELDS = {
    "service_type": "drain_cleaning",
    "start_date": "2026-12-14",
    "property_type": "house",
    "address_area": "Alderbrook Heights",
    "preferred_contact": "email",
    "booking_reference": None,
    "dates_as_written": "Monday the 14th, mornings are best",
}


def test_extracted_fields_accepts_the_documented_example() -> None:
    fields = models.ExtractedFields.model_validate(FIELDS)
    assert fields.service_type is models.ServiceType.drain_cleaning


def test_extracted_fields_requires_every_key() -> None:
    for key in FIELDS:
        partial = {k: v for k, v in FIELDS.items() if k != key}
        with pytest.raises(ValidationError):
            models.ExtractedFields.model_validate(partial)


def test_extracted_fields_rejects_unknown_values_and_keys() -> None:
    with pytest.raises(ValidationError):
        models.ExtractedFields.model_validate({**FIELDS, "service_type": "plumbing"})
    with pytest.raises(ValidationError):
        models.ExtractedFields.model_validate({**FIELDS, "pet_name": "Biscuit"})
    with pytest.raises(ValidationError):
        models.ExtractedFields.model_validate({**FIELDS, "start_date": "12/14"})


def test_classified_intent_source_and_claim_shapes() -> None:
    models.ClassifiedIntent.model_validate({"intent": "booking_request", "confidence": "high"})
    with pytest.raises(ValidationError):
        models.ClassifiedIntent.model_validate({"intent": "nonsense", "confidence": "high"})
    models.Source.model_validate(
        {"file": "pricing.md", "section": "Pricing > Drain cleaning", "page": None, "text": "t"}
    )
    with pytest.raises(ValidationError):
        models.Source.model_validate({"file": "pricing.md", "text": "t"})
    models.Claim.model_validate({"text": "t", "source_index": 0})
    with pytest.raises(ValidationError):
        models.Claim.model_validate({"text": "t", "source_index": -1})


# --- row models ------------------------------------------------------------------------------


def inquiry_row(**over: Any) -> dict[str, Any]:
    return {
        "id": 1,
        "external_id": None,
        "channel": "web_form",
        "received_at": "2026-10-28T10:00:00Z",
        "sender_name": None,
        "sender_email": None,
        "subject": None,
        "body": "hi",
        "thread_id": None,
        "duplicate_of": None,
        "status": "received",
        "route": None,
        "urgency": None,
        "primary_intent": None,
        "failure_stage": None,
        "failure_message": None,
        "is_synthetic": 1,
        "created_at": "2026-10-28T10:00:00Z",
        "updated_at": "2026-10-28T10:00:00Z",
        **over,
    }


def test_inquiry_row_model_reads_a_database_row() -> None:
    inquiry = models.Inquiry.model_validate(inquiry_row(is_synthetic=1, route="escalate"))
    assert inquiry.is_synthetic is True
    assert inquiry.route is models.Route.escalate


def test_row_models_reject_unknown_columns_and_values() -> None:
    with pytest.raises(ValidationError):
        models.Inquiry.model_validate(inquiry_row(surprise=1))
    with pytest.raises(ValidationError):
        models.Inquiry.model_validate(inquiry_row(status="nonsense"))


def test_json_columns_are_parsed_from_text() -> None:
    row = {
        "id": 1,
        "inquiry_id": 1,
        "attempt": 1,
        "model": "m",
        "prompt_version": "understand-v1",
        "intents": '[{"intent": "booking_request", "confidence": "high"}]',
        "primary_intent": "booking_request",
        "primary_confidence": "high",
        "urgency": "normal",
        "sentiment": "neutral",
        "summary": None,
        "safety_net_hit": 0,
        "raw_response": "{}",
        "focused_signals": '["INJECTION_SUSPECTED"]',
        "duration_ms": None,
        "created_at": "x",
    }
    parsed = models.Classification.model_validate(row)
    assert parsed.intents[0].intent is models.Intent.booking_request
    assert parsed.safety_net_hit is False


def test_every_table_has_a_row_model_whose_fields_match_its_columns() -> None:
    conn = connect(":memory:")
    migrate(conn)
    by_table = {
        "inquiries": models.Inquiry,
        "screenings": models.Screening,
        "classifications": models.Classification,
        "extractions": models.Extraction,
        "escalations": models.Escalation,
        "retrievals": models.Retrieval,
        "drafts": models.Draft,
        "draft_checks": models.DraftCheck,
        "reviews": models.Review,
        "exports": models.Export,
        "audit_events": models.AuditEvent,
        "settings": models.Setting,
    }
    for table, model in by_table.items():
        columns = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}  # noqa: S608
        assert set(model.model_fields) == columns, table
