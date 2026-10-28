"""Audit events: the reviewer-facing history of what happened to an inquiry.

An event holds ids, stage names, status names, timings and codes, never message or draft text
(CLAUDE.md rule 4). `record_event` is the only code that writes to `audit_events`, and it refuses
a payload that could carry text:

- keys are plain snake_case names;
- values are numbers, booleans, null, or short code-like tokens (no spaces, at most 64
  characters, no `@`, `/` or newlines), or flat lists of those;
- a token that appears as a word in the inquiry's own text is refused unless it is a known code,
  so a single word lifted from the message cannot slip through;
- a rejection never repeats the rejected value, because the exception may be logged.
"""

import json
import math
import re
import sqlite3
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any

from citedesk import models
from citedesk.db import utc_now
from citedesk.models import AuditEvent, AuditEventType, InquiryStatus, Stage
from citedesk.safety import EMERGENCY_PATTERNS
from citedesk.screening import DERIVED_FLAGS, SPAM_SIGNALS, STRONG, WEAK

KEY = re.compile(r"^[a-z][a-z0-9_]{0,40}$")
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:+-]{0,63}")
PHONE_LIKE = re.compile(r"\d{3}[-.]\d{4}")
MAX_LIST = 50
MAX_JSON_CHARS = 2000

# Every value of every enumeration in models.py: codes the system itself produces.
KNOWN_CODES: frozenset[str] = frozenset(
    member.value
    for enum_class in vars(models).values()
    if isinstance(enum_class, type)
    and issubclass(enum_class, StrEnum)
    and enum_class is not StrEnum
    for member in enum_class
)


# Names the screening code produces. Several are also ordinary words ("sewage", "flooding"), so a
# customer who writes one must not make the audit event for it fail.
KNOWN_CODES = (
    KNOWN_CODES
    | frozenset(EMERGENCY_PATTERNS)
    | frozenset(STRONG)
    | frozenset(WEAK)
    | frozenset(SPAM_SIGNALS)
    | frozenset(DERIVED_FLAGS)
)


class PayloadRejected(ValueError):
    """The payload could carry message text. The message never repeats the offending value."""


def _check_scalar(key: str, value: Any, protect: Sequence[str]) -> None:
    if value is None or isinstance(value, bool | int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise PayloadRejected(f"value for {key!r} is not a finite number")
        return
    if not isinstance(value, str):
        raise PayloadRejected(f"value for {key!r} has a type that is not allowed")
    if (
        not TOKEN.fullmatch(value)
        or PHONE_LIKE.search(value)
        or (value.isdigit() and len(value) >= 7)
    ):
        raise PayloadRejected(f"value for {key!r} is not a short code-like token")
    if value in KNOWN_CODES:
        return
    for text in protect:
        pattern = rf"(?<![A-Za-z0-9]){re.escape(value)}(?![A-Za-z0-9])"
        if re.search(pattern, text, flags=re.IGNORECASE):
            raise PayloadRejected(f"value for {key!r} appears in the message text")


def validate_payload(payload: Mapping[str, Any], *, protect: Sequence[str] = ()) -> dict[str, Any]:
    """Return a copy of the payload if it is safe to store, otherwise raise PayloadRejected."""
    clean: dict[str, Any] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not KEY.fullmatch(key):
            raise PayloadRejected("a payload key is not a plain snake_case name")
        if isinstance(value, list):
            if len(value) > MAX_LIST:
                raise PayloadRejected(f"list for {key!r} has more than {MAX_LIST} items")
            for item in value:
                if isinstance(item, list | dict):
                    raise PayloadRejected(f"payload must be flat; {key!r} holds a nested value")
                _check_scalar(key, item, protect)
            clean[key] = list(value)
        elif isinstance(value, dict):
            raise PayloadRejected(f"payload must be flat; {key!r} holds a nested value")
        else:
            _check_scalar(key, value, protect)
            clean[key] = value
    if len(json.dumps(clean, ensure_ascii=False)) > MAX_JSON_CHARS:
        raise PayloadRejected(f"payload is too large (over {MAX_JSON_CHARS} characters)")
    return clean


def _message_texts(conn: sqlite3.Connection, inquiry_id: int) -> list[str]:
    row = conn.execute(
        "SELECT body, subject, sender_name, sender_email FROM inquiries WHERE id = ?", (inquiry_id,)
    ).fetchone()
    return [] if row is None else [str(v) for v in tuple(row) if v]


def record_event(
    conn: sqlite3.Connection,
    *,
    event_type: AuditEventType | str,
    inquiry_id: int | None = None,
    stage: Stage | str | None = None,
    from_status: InquiryStatus | str | None = None,
    to_status: InquiryStatus | str | None = None,
    payload: Mapping[str, Any] | None = None,
    request_id: str | None = None,
    duration_ms: int | None = None,
    now: str | None = None,
) -> int:
    """Write one audit event. Raises PayloadRejected, and writes nothing, if the payload or the
    request id could carry message text."""
    kind = AuditEventType(event_type)
    protect = _message_texts(conn, inquiry_id) if inquiry_id is not None else []
    clean = validate_payload(payload or {}, protect=protect)
    if request_id is not None and not TOKEN.fullmatch(request_id):
        raise PayloadRejected("request_id is not a short code-like token")
    cursor = conn.execute(
        "INSERT INTO audit_events (inquiry_id, event_type, stage, from_status, to_status, payload, "
        "request_id, duration_ms, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            inquiry_id,
            kind.value,
            None if stage is None else Stage(stage).value,
            None if from_status is None else InquiryStatus(from_status).value,
            None if to_status is None else InquiryStatus(to_status).value,
            json.dumps(clean, ensure_ascii=False),
            request_id,
            duration_ms,
            now or utc_now(),
        ),
    )
    if cursor.lastrowid is None:
        raise RuntimeError("INSERT did not produce a row id")
    return cursor.lastrowid


def list_events(conn: sqlite3.Connection, inquiry_id: int) -> list[AuditEvent]:
    rows = conn.execute(
        "SELECT * FROM audit_events WHERE inquiry_id = ? ORDER BY created_at, id", (inquiry_id,)
    ).fetchall()
    return [AuditEvent.from_row(row) for row in rows]
