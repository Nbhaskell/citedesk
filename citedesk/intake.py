"""Intake: check an incoming message, screen it, and store it before anything else happens.

`submit` is the one way an inquiry enters the system. In a single transaction it validates the
message, runs the screening detectors (pure code, no model), and writes the inquiry with status
`received` together with its screening result. Sensitive numbers are masked before the first
write, so an unmasked number is never stored, not even briefly. If screening itself fails, nothing
is stored: refusing is safer than keeping text that was never checked.

The pipeline's screen stage (citedesk.pipeline) later applies the stored result.
"""

import csv
import io
import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError, field_validator

from citedesk import repo
from citedesk.config import Settings
from citedesk.db import transaction, utc_now
from citedesk.models import Channel, InquiryStatus
from citedesk.screening import screen
from citedesk.textnorm import normalise

MAX_IMPORT_RECORDS = 5000
FUTURE_SKEW = timedelta(minutes=5)
CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class IntakeError(Exception):
    """An inquiry could not be accepted. Messages never contain the customer's text."""


class InvalidInquiry(IntakeError, ValueError):
    """The message broke a rule (too long, in the future, and so on)."""


class DuplicateExternalId(IntakeError):
    def __init__(self, existing_id: int) -> None:
        super().__init__("an inquiry with this channel and external id already exists")
        self.existing_id = existing_id


class IntakeFailure(IntakeError):
    """Screening crashed, so nothing was stored."""


class ImportFormatError(Exception):
    """A bulk file is unusable as a whole."""


def _clean(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = CONTROL_CHARACTERS.sub("", value.replace("\r\n", "\n").replace("\r", "\n"))
    return text.strip()


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _format_time(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


Short = Annotated[str, StringConstraints(max_length=200)]


class NewInquiry(BaseModel):
    """What a caller may send. Anything else, such as labels, is refused."""

    model_config = ConfigDict(extra="forbid")

    external_id: Short | None = None
    channel: Channel = Channel.web_form
    sender_name: Short | None = None
    sender_email: Annotated[str, StringConstraints(max_length=254)] | None = None
    subject: Annotated[str, StringConstraints(max_length=300)] | None = None
    body: Annotated[str, StringConstraints(min_length=1)]
    received_at: str | None = None
    thread_id: Short | None = None

    @field_validator("*", mode="before")
    @classmethod
    def clean_text(cls, value: Any) -> Any:
        return _clean(value)

    @field_validator(
        "external_id", "sender_name", "sender_email", "subject", "thread_id", mode="after"
    )
    @classmethod
    def blank_is_none(cls, value: str | None) -> str | None:
        return value or None

    @field_validator("sender_email", mode="after")
    @classmethod
    def valid_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not EMAIL.match(value):
            raise ValueError("sender_email is not a valid email address")
        return value.lower()

    @field_validator("received_at", mode="after")
    @classmethod
    def valid_time(cls, value: str | None) -> str | None:
        if not value:
            return None
        try:
            return _format_time(_parse_time(value))
        except ValueError as error:
            raise ValueError("received_at must be an ISO 8601 date and time") from error


@dataclass(frozen=True)
class SubmitResult:
    id: int
    status: InquiryStatus
    duplicate_of: int | None
    sensitive_data_masked: bool


def _sender_key(inquiry: NewInquiry) -> tuple[str | None, str | None]:
    return inquiry.sender_email, inquiry.sender_name.lower() if inquiry.sender_name else None


def _content_key(subject: str | None, body: str) -> str:
    return normalise(f"{subject or ''}\n{body}")


def _find_content_duplicate(
    conn: sqlite3.Connection,
    inquiry: NewInquiry,
    subject: str | None,
    body: str,
    received_at: str,
    window_hours: int,
) -> int | None:
    email, name = _sender_key(inquiry)
    if window_hours <= 0 or (email is None and name is None):
        return None
    centre = _parse_time(received_at)
    low, high = (
        _format_time(centre - timedelta(hours=window_hours)),
        _format_time(centre + timedelta(hours=window_hours)),
    )
    rows = conn.execute(
        "SELECT id, subject, body FROM inquiries WHERE duplicate_of IS NULL "
        "AND received_at BETWEEN ? AND ? "
        "AND ((? IS NOT NULL AND sender_email = ?) "
        "OR (? IS NULL AND sender_email IS NULL AND ? IS NOT NULL AND lower(sender_name) = ?)) "
        "ORDER BY id",
        (low, high, email, email, email, name, name),
    ).fetchall()
    wanted = _content_key(subject, body)
    for row in rows:
        if _content_key(row["subject"], row["body"]) == wanted:
            return int(row["id"])
    return None


def submit(
    conn: sqlite3.Connection, inquiry: NewInquiry, settings: Settings, *, now: str | None = None
) -> SubmitResult:
    """Validate, screen and store one inquiry as `received`. Nothing else runs yet."""
    stamp = now or utc_now()
    if len(inquiry.body) > settings.max_body_chars:
        raise InvalidInquiry(f"body is longer than {settings.max_body_chars} characters")
    received_at = inquiry.received_at or stamp
    if _parse_time(received_at) > _parse_time(stamp) + FUTURE_SKEW:
        raise InvalidInquiry("received_at is in the future")

    try:
        outcome = screen(inquiry.subject, inquiry.body, spam_threshold=settings.spam_threshold)
    except Exception as error:
        raise IntakeFailure("screening failed, so nothing was stored") from error

    with transaction(conn):
        if inquiry.external_id is not None:
            existing = repo.find_by_external_id(conn, inquiry.channel, inquiry.external_id)
            if existing is not None:
                raise DuplicateExternalId(existing.id)
        duplicate_of = _find_content_duplicate(
            conn,
            inquiry,
            outcome.subject,
            outcome.body,
            received_at,
            settings.duplicate_window_hours,
        )
        inquiry_id = repo.insert_inquiry(
            conn,
            channel=inquiry.channel,
            body=outcome.body,
            received_at=received_at,
            external_id=inquiry.external_id,
            sender_name=inquiry.sender_name,
            sender_email=inquiry.sender_email,
            subject=outcome.subject,
            thread_id=inquiry.thread_id,
            duplicate_of=duplicate_of,
            is_synthetic=settings.synthetic_data,
            now=stamp,
        )
        repo.upsert_screening(
            conn,
            inquiry_id=inquiry_id,
            spam_score=outcome.spam_score,
            injection_flags=outcome.injection_flags,
            sensitive_data_masked=bool(outcome.sensitive_kinds),
            result=outcome.result,
            now=stamp,
        )
    return SubmitResult(
        id=inquiry_id,
        status=InquiryStatus.received,
        duplicate_of=duplicate_of,
        sensitive_data_masked=bool(outcome.sensitive_kinds),
    )


# --- bulk files ------------------------------------------------------------------------------


@dataclass(frozen=True)
class ParsedRecord:
    line: int
    record: dict[str, Any] | None
    error: str | None


@dataclass(frozen=True)
class Rejection:
    line: int
    code: str


@dataclass
class ImportSummary:
    created: int = 0
    already_imported: int = 0
    linked_duplicates: int = 0
    rejected: list[Rejection] = field(default_factory=list)
    ids: list[int] = field(default_factory=list)


def parse_jsonl(text: str) -> list[ParsedRecord]:
    parsed: list[ParsedRecord] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        if len(parsed) >= MAX_IMPORT_RECORDS:
            raise ImportFormatError(f"too many records (limit {MAX_IMPORT_RECORDS})")
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            parsed.append(ParsedRecord(number, None, "invalid_json"))
            continue
        if not isinstance(record, dict):
            parsed.append(ParsedRecord(number, None, "not_an_object"))
            continue
        parsed.append(ParsedRecord(number, record, None))
    return parsed


def parse_csv(text: str) -> list[ParsedRecord]:
    reader = csv.DictReader(io.StringIO(text))
    columns = set(reader.fieldnames or [])
    if not columns:
        raise ImportFormatError("the file has no header row")
    unknown = sorted(columns - set(NewInquiry.model_fields))
    if unknown:
        raise ImportFormatError(f"unknown column(s): {', '.join(unknown)}")
    if "body" not in columns:
        raise ImportFormatError("missing required column: body")
    parsed: list[ParsedRecord] = []
    for row in reader:
        if len(parsed) >= MAX_IMPORT_RECORDS:
            raise ImportFormatError(f"too many records (limit {MAX_IMPORT_RECORDS})")
        if None in row:
            parsed.append(ParsedRecord(reader.line_num, None, "invalid_row"))
            continue
        parsed.append(
            ParsedRecord(
                reader.line_num,
                {k: (v if v not in ("", None) else None) for k, v in row.items()},
                None,
            )
        )
    return parsed


def import_records(
    conn: sqlite3.Connection, records: list[ParsedRecord], settings: Settings
) -> ImportSummary:
    """Store each record on its own. A bad record never stops the others, and the summary holds
    line numbers and codes only, never message text."""
    summary = ImportSummary()
    for item in records:
        if item.error is not None or item.record is None:
            summary.rejected.append(Rejection(item.line, item.error or "invalid"))
            continue
        try:
            result = submit(conn, NewInquiry.model_validate(item.record), settings)
        except (ValidationError, InvalidInquiry):
            summary.rejected.append(Rejection(item.line, "invalid"))
        except DuplicateExternalId:
            summary.already_imported += 1
        except IntakeFailure:
            summary.rejected.append(Rejection(item.line, "screening_failed"))
        else:
            summary.created += 1
            summary.ids.append(result.id)
            if result.duplicate_of is not None:
                summary.linked_duplicates += 1
    return summary
