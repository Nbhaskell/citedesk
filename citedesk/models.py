"""Enumerations and row models. The single source of truth for values in code.

Names and values are those of docs/BACKEND_SCHEMA.md; tests keep this file, that document and the
database CHECK constraints in step. Row models mirror the tables column for column.
"""

import json
import re
import sqlite3
from enum import StrEnum
from typing import Annotated, Any, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

# --- enumerations (BACKEND_SCHEMA.md section 1) ----------------------------------------------


class Channel(StrEnum):
    web_form = "web_form"
    email = "email"
    import_ = "import"
    webhook = "webhook"


class Intent(StrEnum):
    pricing_question = "pricing_question"
    availability_question = "availability_question"
    booking_request = "booking_request"
    booking_change = "booking_change"
    cancellation = "cancellation"
    policy_question = "policy_question"
    service_question = "service_question"
    complaint = "complaint"
    health_or_safety = "health_or_safety"
    billing_question = "billing_question"
    partnership_or_sales = "partnership_or_sales"
    spam = "spam"
    other = "other"


class Urgency(StrEnum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class Sentiment(StrEnum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"
    angry = "angry"


class Confidence(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class Route(StrEnum):
    draft_reply = "draft_reply"
    request_details = "request_details"
    escalate = "escalate"
    archive = "archive"


class InquiryStatus(StrEnum):
    received = "received"
    screened = "screened"
    classified = "classified"
    routed = "routed"
    drafted = "drafted"
    needs_review = "needs_review"
    escalated = "escalated"
    approved = "approved"
    rejected = "rejected"
    exported = "exported"
    resolved = "resolved"
    archived = "archived"
    failed = "failed"


class ReasonCode(StrEnum):
    HEALTH_SAFETY = "HEALTH_SAFETY"
    COMPLAINT = "COMPLAINT"
    REFUND_OR_DISPUTE = "REFUND_OR_DISPUTE"
    LEGAL_THREAT = "LEGAL_THREAT"
    POLICY_EXCEPTION_REQUEST = "POLICY_EXCEPTION_REQUEST"
    INJECTION_SUSPECTED = "INJECTION_SUSPECTED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    NOT_IN_KNOWLEDGE_BASE = "NOT_IN_KNOWLEDGE_BASE"
    UNVERIFIED_FIGURE = "UNVERIFIED_FIGURE"
    MANUAL = "MANUAL"


class CheckCode(StrEnum):
    FIGURES_GROUNDED = "FIGURES_GROUNDED"
    NO_COMMITMENT = "NO_COMMITMENT"
    CLAIMS_HAVE_SOURCES = "CLAIMS_HAVE_SOURCES"
    STRUCTURE = "STRUCTURE"
    NO_INJECTION_ECHO = "NO_INJECTION_ECHO"
    ADDRESSES_ASK = "ADDRESSES_ASK"


class DraftKind(StrEnum):
    reply = "reply"
    request_details = "request_details"
    holding_reply = "holding_reply"


class DraftStatus(StrEnum):
    ready = "ready"
    blocked = "blocked"
    approved = "approved"
    rejected = "rejected"
    superseded = "superseded"


class Decision(StrEnum):
    approve = "approve"
    edit_approve = "edit_approve"
    reject = "reject"
    escalate = "escalate"
    resolve = "resolve"


class ServiceType(StrEnum):
    emergency_repair = "emergency_repair"
    drain_cleaning = "drain_cleaning"
    leak_repair = "leak_repair"
    sewer_line_repair = "sewer_line_repair"
    water_heater = "water_heater"
    fixture_installation = "fixture_installation"
    inspection = "inspection"
    # the electrical trade (D-098)
    panel_upgrade = "panel_upgrade"
    outlet_and_switch = "outlet_and_switch"
    lighting_installation = "lighting_installation"
    ev_charger_installation = "ev_charger_installation"
    wiring_repair = "wiring_repair"
    other = "other"
    unknown = "unknown"


class PropertyType(StrEnum):
    house = "house"
    apartment = "apartment"
    commercial = "commercial"
    other = "other"
    unknown = "unknown"


class Stage(StrEnum):
    screen = "screen"
    understand = "understand"
    route = "route"
    retrieve = "retrieve"
    draft = "draft"
    check = "check"


# --- values that appear in CHECK constraints but not in the section 1 table ------------------


class ScreeningResult(StrEnum):
    clean = "clean"
    spam = "spam"
    injection_suspected = "injection_suspected"


class EscalationSource(StrEnum):
    rule = "rule"
    safety_net = "safety_net"
    check = "check"
    reviewer = "reviewer"


class ExportMethod(StrEnum):
    copy = "copy"
    mail_draft = "mail_draft"


class AuditEventType(StrEnum):
    """Documented in a comment on audit_events.event_type; the column has no CHECK."""

    stage_started = "stage_started"
    stage_finished = "stage_finished"
    stage_failed = "stage_failed"
    route_decided = "route_decided"
    check_failed = "check_failed"
    review_recorded = "review_recorded"
    status_changed = "status_changed"
    inquiry_deleted = "inquiry_deleted"


# --- JSON shapes (BACKEND_SCHEMA.md section 4) -----------------------------------------------


def parse_json(value: Any) -> Any:
    """JSON columns hold text; accept either the text or the already parsed value."""
    return json.loads(value) if isinstance(value, str) else value


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClassifiedIntent(Strict):
    intent: Intent
    confidence: Confidence


class ExtractedFields(Strict):
    """Every key is present; an unknown value is null."""

    service_type: ServiceType | None
    start_date: str | None
    property_type: PropertyType | None
    address_area: str | None
    preferred_contact: str | None
    booking_reference: str | None
    dates_as_written: str | None

    @field_validator("start_date")
    @classmethod
    def iso_date(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("start_date must be YYYY-MM-DD or null")
        return value


class Source(Strict):
    file: str
    section: str
    page: int | None
    text: str


class Claim(Strict):
    text: str
    source_index: int = Field(ge=0)


JsonList = Annotated[list[Any], BeforeValidator(parse_json)]


# --- row models, one per table ---------------------------------------------------------------


class Row(Strict):
    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Self:
        return cls.model_validate(dict(row))


class Inquiry(Row):
    id: int
    external_id: str | None
    channel: Channel
    received_at: str
    sender_name: str | None
    sender_email: str | None
    subject: str | None
    body: str
    thread_id: str | None
    duplicate_of: int | None
    status: InquiryStatus
    route: Route | None
    urgency: Urgency | None
    primary_intent: Intent | None
    failure_stage: Stage | None
    failure_message: str | None
    is_synthetic: bool
    created_at: str
    updated_at: str


class Screening(Row):
    id: int
    inquiry_id: int
    spam_score: float
    injection_flags: Annotated[list[str], BeforeValidator(parse_json)]
    sensitive_data_masked: bool
    result: ScreeningResult
    created_at: str


class Classification(Row):
    id: int
    inquiry_id: int
    attempt: int
    model: str
    prompt_version: str
    intents: Annotated[list[ClassifiedIntent], BeforeValidator(parse_json)]
    primary_intent: Intent
    primary_confidence: Confidence
    urgency: Urgency
    sentiment: Sentiment
    summary: str | None
    safety_net_hit: bool
    raw_response: str
    focused_signals: Annotated[list[ReasonCode], BeforeValidator(parse_json)]
    duration_ms: int | None
    created_at: str


class Extraction(Row):
    id: int
    inquiry_id: int
    classification_id: int
    fields: Annotated[ExtractedFields, BeforeValidator(parse_json)]
    missing_fields: Annotated[list[str], BeforeValidator(parse_json)]
    created_at: str


class Escalation(Row):
    id: int
    inquiry_id: int
    reason_code: ReasonCode
    detail: str | None
    source: EscalationSource
    resolved: bool
    resolved_at: str | None
    created_at: str


class Retrieval(Row):
    id: int
    inquiry_id: int
    question: str
    declined: bool
    kb_answer: str | None
    sources: Annotated[list[Source], BeforeValidator(parse_json)]
    duration_ms: int | None
    created_at: str


class Draft(Row):
    id: int
    inquiry_id: int
    version: int
    kind: DraftKind
    subject: str | None
    body: str
    claims: Annotated[list[Claim], BeforeValidator(parse_json)]
    model: str
    prompt_version: str
    guidance: str | None
    status: DraftStatus
    duration_ms: int | None
    created_at: str


class DraftCheck(Row):
    id: int
    draft_id: int
    check_code: CheckCode
    blocking: bool
    passed: bool
    detail: Annotated[dict[str, Any] | None, BeforeValidator(parse_json)]
    created_at: str


class Review(Row):
    id: int
    inquiry_id: int
    draft_id: int | None
    decision: Decision
    edited_body: str | None
    reason: str | None
    reviewer: str
    review_seconds: int | None
    created_at: str


class Export(Row):
    id: int
    draft_id: int
    method: ExportMethod
    external_ref: str | None
    created_at: str


class AuditEvent(Row):
    id: int
    inquiry_id: int | None
    event_type: AuditEventType
    stage: Stage | None
    from_status: InquiryStatus | None
    to_status: InquiryStatus | None
    payload: Annotated[dict[str, Any], BeforeValidator(parse_json)]
    request_id: str | None
    duration_ms: int | None
    created_at: str


class Setting(Row):
    key: str
    value: str
    updated_at: str
