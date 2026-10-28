"""Repository functions: plain SQL, one group per table, no ORM.

Every function takes an open connection first. Timestamps default to the current UTC time and can
be passed as `now` for tests. Inquiry status is deliberately not writable here; it changes only
through the state machine in citedesk.state.
"""

import json
import sqlite3
from collections.abc import Sequence
from typing import Any, cast

from citedesk.db import transaction, utc_now
from citedesk.models import (
    Channel,
    CheckCode,
    Claim,
    Classification,
    ClassifiedIntent,
    Confidence,
    Decision,
    Draft,
    DraftCheck,
    DraftKind,
    DraftStatus,
    Escalation,
    EscalationSource,
    Export,
    ExportMethod,
    ExtractedFields,
    Extraction,
    Inquiry,
    InquiryStatus,
    Intent,
    ReasonCode,
    Retrieval,
    Review,
    Route,
    Row,
    Screening,
    ScreeningResult,
    Sentiment,
    Source,
    Urgency,
)

MAX_ESCALATION_DETAIL = 200


class DraftBlocked(Exception):
    """A draft with a failed blocking check cannot be made ready or approved."""


# --- helpers ---------------------------------------------------------------------------------


def _now(now: str | None) -> str:
    return now or utc_now()


def _one[M: Row](
    conn: sqlite3.Connection, model: type[M], sql: str, params: tuple[Any, ...]
) -> M | None:
    row = conn.execute(sql, params).fetchone()
    return None if row is None else model.from_row(row)


def _many[M: Row](
    conn: sqlite3.Connection, model: type[M], sql: str, params: tuple[Any, ...]
) -> list[M]:
    return [model.from_row(row) for row in conn.execute(sql, params).fetchall()]


def _returning_id(cursor: sqlite3.Cursor) -> int:
    """The id from an INSERT ... RETURNING id. All rows are fetched so the statement finishes."""
    rows = cursor.fetchall()
    return int(rows[0]["id"])


def _last_id(cursor: sqlite3.Cursor) -> int:
    if cursor.lastrowid is None:
        raise RuntimeError("INSERT did not produce a row id")
    return cursor.lastrowid


def _json(items: Sequence[Any]) -> str:
    return json.dumps(
        [i.model_dump(mode="json") if hasattr(i, "model_dump") else i for i in items],
        ensure_ascii=False,
    )


# --- inquiries -------------------------------------------------------------------------------


def insert_inquiry(
    conn: sqlite3.Connection,
    *,
    channel: Channel | str,
    body: str,
    received_at: str | None = None,
    external_id: str | None = None,
    sender_name: str | None = None,
    sender_email: str | None = None,
    subject: str | None = None,
    thread_id: str | None = None,
    duplicate_of: int | None = None,
    is_synthetic: bool = True,
    now: str | None = None,
) -> int:
    stamp = _now(now)
    cursor = conn.execute(
        "INSERT INTO inquiries (external_id, channel, received_at, sender_name, sender_email, "
        "subject, body, thread_id, duplicate_of, is_synthetic, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            external_id,
            Channel(channel).value,
            received_at or stamp,
            sender_name,
            sender_email,
            subject,
            body,
            thread_id,
            duplicate_of,
            int(is_synthetic),
            stamp,
            stamp,
        ),
    )
    return _last_id(cursor)


def get_inquiry(conn: sqlite3.Connection, inquiry_id: int) -> Inquiry | None:
    return _one(conn, Inquiry, "SELECT * FROM inquiries WHERE id = ?", (inquiry_id,))


def find_by_external_id(
    conn: sqlite3.Connection, channel: Channel | str, external_id: str
) -> Inquiry | None:
    return _one(
        conn,
        Inquiry,
        "SELECT * FROM inquiries WHERE channel = ? AND external_id = ?",
        (Channel(channel).value, external_id),
    )


UPDATABLE = {
    "route": Route,
    "urgency": Urgency,
    "primary_intent": Intent,
    "duplicate_of": None,
    "thread_id": None,
}


def update_inquiry(
    conn: sqlite3.Connection, inquiry_id: int, *, now: str | None = None, **fields: Any
) -> None:
    """Change classification results and links. Status and the message itself cannot change."""
    if not fields:
        raise ValueError("nothing to update")
    values: list[Any] = []
    for name, value in fields.items():
        if name not in UPDATABLE:
            hint = " (use the state machine)" if name == "status" else ""
            raise ValueError(f"cannot update {name}{hint}")
        enum_class = UPDATABLE[name]
        values.append(enum_class(value).value if enum_class and value is not None else value)
    assignments = ", ".join(f"{name} = ?" for name in fields)
    cursor = conn.execute(
        f"UPDATE inquiries SET {assignments}, updated_at = ? WHERE id = ?",  # noqa: S608 (names are whitelisted)
        (*values, _now(now), inquiry_id),
    )
    if cursor.rowcount == 0:
        raise LookupError(f"no inquiry {inquiry_id}")


def list_inquiries(
    conn: sqlite3.Connection,
    *,
    statuses: Sequence[InquiryStatus | str] | None = None,
    limit: int | None = None,
) -> list[Inquiry]:
    sql = "SELECT * FROM inquiries"
    params: list[Any] = []
    if statuses is not None:
        marks = ", ".join("?" for _ in statuses)
        sql += f" WHERE status IN ({marks})"  # noqa: S608 (placeholders only)
        params += [InquiryStatus(s).value for s in statuses]
    sql += " ORDER BY id"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    return _many(conn, Inquiry, sql, tuple(params))


def review_queue(conn: sqlite3.Connection) -> list[Inquiry]:
    """Needs attention first, then by urgency, then oldest first (BACKEND_SCHEMA.md section 6)."""
    return _many(
        conn,
        Inquiry,
        "SELECT i.* FROM inquiries i WHERE i.status IN ('needs_review', 'escalated', 'failed') "
        "ORDER BY CASE i.urgency WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 "
        "ELSE 3 END, i.received_at ASC, i.id ASC",
        (),
    )


# --- screenings ------------------------------------------------------------------------------


def upsert_screening(
    conn: sqlite3.Connection,
    *,
    inquiry_id: int,
    spam_score: float,
    injection_flags: Sequence[str],
    sensitive_data_masked: bool,
    result: ScreeningResult | str,
    now: str | None = None,
) -> int:
    cursor = conn.execute(
        "INSERT INTO screenings (inquiry_id, spam_score, injection_flags, sensitive_data_masked, "
        "result, created_at) VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(inquiry_id) DO UPDATE SET spam_score = excluded.spam_score, "
        "injection_flags = excluded.injection_flags, "
        "sensitive_data_masked = excluded.sensitive_data_masked, result = excluded.result, "
        "created_at = excluded.created_at RETURNING id",
        (
            inquiry_id,
            spam_score,
            json.dumps(list(injection_flags)),
            int(sensitive_data_masked),
            ScreeningResult(result).value,
            _now(now),
        ),
    )
    return _returning_id(cursor)


def get_screening(conn: sqlite3.Connection, inquiry_id: int) -> Screening | None:
    return _one(conn, Screening, "SELECT * FROM screenings WHERE inquiry_id = ?", (inquiry_id,))


# --- classifications and extractions ---------------------------------------------------------


def insert_classification(
    conn: sqlite3.Connection,
    *,
    inquiry_id: int,
    model: str,
    prompt_version: str,
    intents: Sequence[ClassifiedIntent],
    primary_intent: Intent | str,
    primary_confidence: Confidence | str,
    urgency: Urgency | str,
    sentiment: Sentiment | str,
    summary: str | None,
    safety_net_hit: bool,
    raw_response: str,
    duration_ms: int | None = None,
    now: str | None = None,
) -> int:
    with transaction(conn):
        attempt = conn.execute(
            "SELECT COALESCE(MAX(attempt), 0) + 1 AS n FROM classifications WHERE inquiry_id = ?",
            (inquiry_id,),
        ).fetchone()["n"]
        cursor = conn.execute(
            "INSERT INTO classifications (inquiry_id, attempt, model, prompt_version, intents, "
            "primary_intent, primary_confidence, urgency, sentiment, summary, safety_net_hit, "
            "raw_response, duration_ms, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                inquiry_id,
                attempt,
                model,
                prompt_version,
                _json(intents),
                Intent(primary_intent).value,
                Confidence(primary_confidence).value,
                Urgency(urgency).value,
                Sentiment(sentiment).value,
                summary,
                int(safety_net_hit),
                raw_response,
                duration_ms,
                _now(now),
            ),
        )
        return _last_id(cursor)


def latest_classification(conn: sqlite3.Connection, inquiry_id: int) -> Classification | None:
    return _one(
        conn,
        Classification,
        "SELECT * FROM classifications WHERE inquiry_id = ? ORDER BY attempt DESC LIMIT 1",
        (inquiry_id,),
    )


def insert_extraction(
    conn: sqlite3.Connection,
    *,
    inquiry_id: int,
    classification_id: int,
    fields: ExtractedFields,
    missing_fields: Sequence[str],
    now: str | None = None,
) -> int:
    owner = conn.execute(
        "SELECT inquiry_id FROM classifications WHERE id = ?", (classification_id,)
    ).fetchone()
    if owner is None or owner["inquiry_id"] != inquiry_id:
        raise ValueError(
            f"classification {classification_id} does not belong to inquiry {inquiry_id}"
        )
    cursor = conn.execute(
        "INSERT INTO extractions "
        "(inquiry_id, classification_id, fields, missing_fields, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            inquiry_id,
            classification_id,
            fields.model_dump_json(),
            json.dumps(list(missing_fields)),
            _now(now),
        ),
    )
    return _last_id(cursor)


def latest_extraction(conn: sqlite3.Connection, inquiry_id: int) -> Extraction | None:
    return _one(
        conn,
        Extraction,
        "SELECT * FROM extractions WHERE inquiry_id = ? ORDER BY id DESC LIMIT 1",
        (inquiry_id,),
    )


# --- escalations -----------------------------------------------------------------------------


def insert_escalation(
    conn: sqlite3.Connection,
    *,
    inquiry_id: int,
    reason_code: ReasonCode | str,
    source: EscalationSource | str,
    detail: str | None = None,
    now: str | None = None,
) -> int:
    """Record why an inquiry was escalated. An open escalation with the same reason is reused,
    so re-running a stage does not pile up duplicates."""
    if detail is not None and len(detail) > MAX_ESCALATION_DETAIL:
        raise ValueError(
            f"detail must be at most {MAX_ESCALATION_DETAIL} characters and hold no customer text"
        )
    code = ReasonCode(reason_code).value
    with transaction(conn):
        existing = conn.execute(
            "SELECT id FROM escalations WHERE inquiry_id = ? AND reason_code = ? AND resolved = 0",
            (inquiry_id, code),
        ).fetchone()
        if existing is not None:
            return int(existing["id"])
        cursor = conn.execute(
            "INSERT INTO escalations (inquiry_id, reason_code, detail, source, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (inquiry_id, code, detail, EscalationSource(source).value, _now(now)),
        )
        return _last_id(cursor)


def list_escalations(
    conn: sqlite3.Connection, inquiry_id: int, *, open_only: bool = False
) -> list[Escalation]:
    sql = "SELECT * FROM escalations WHERE inquiry_id = ?"
    if open_only:
        sql += " AND resolved = 0"
    return _many(conn, Escalation, sql + " ORDER BY id", (inquiry_id,))


def resolve_escalations(
    conn: sqlite3.Connection, inquiry_id: int, *, now: str | None = None
) -> int:
    cursor = conn.execute(
        "UPDATE escalations SET resolved = 1, resolved_at = ? "
        "WHERE inquiry_id = ? AND resolved = 0",
        (_now(now), inquiry_id),
    )
    return cursor.rowcount


# --- retrievals ------------------------------------------------------------------------------


def insert_retrieval(
    conn: sqlite3.Connection,
    *,
    inquiry_id: int,
    question: str,
    declined: bool,
    kb_answer: str | None,
    sources: Sequence[Source],
    duration_ms: int | None = None,
    now: str | None = None,
) -> int:
    cursor = conn.execute(
        "INSERT INTO retrievals (inquiry_id, question, declined, kb_answer, sources, duration_ms, "
        "created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (inquiry_id, question, int(declined), kb_answer, _json(sources), duration_ms, _now(now)),
    )
    return _last_id(cursor)


def list_retrievals(conn: sqlite3.Connection, inquiry_id: int) -> list[Retrieval]:
    return _many(
        conn, Retrieval, "SELECT * FROM retrievals WHERE inquiry_id = ? ORDER BY id", (inquiry_id,)
    )


# --- drafts and draft checks -----------------------------------------------------------------


def insert_draft(
    conn: sqlite3.Connection,
    *,
    inquiry_id: int,
    kind: DraftKind | str,
    body: str,
    model: str,
    prompt_version: str,
    subject: str | None = None,
    claims: Sequence[Claim] = (),
    guidance: str | None = None,
    status: DraftStatus | str = DraftStatus.blocked,
    duration_ms: int | None = None,
    now: str | None = None,
) -> int:
    """Add the next version of a draft. It starts as blocked: a draft is not ready until its
    checks have run, and set_draft_status will not make it ready if a blocking check failed."""
    with transaction(conn):
        version = conn.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 AS v FROM drafts WHERE inquiry_id = ?",
            (inquiry_id,),
        ).fetchone()["v"]
        cursor = conn.execute(
            "INSERT INTO drafts (inquiry_id, version, kind, subject, body, claims, model, "
            "prompt_version, guidance, status, duration_ms, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                inquiry_id,
                version,
                DraftKind(kind).value,
                subject,
                body,
                _json(claims),
                model,
                prompt_version,
                guidance,
                DraftStatus(status).value,
                duration_ms,
                _now(now),
            ),
        )
        return _last_id(cursor)


def get_draft(conn: sqlite3.Connection, draft_id: int) -> Draft | None:
    return _one(conn, Draft, "SELECT * FROM drafts WHERE id = ?", (draft_id,))


def latest_draft(conn: sqlite3.Connection, inquiry_id: int) -> Draft | None:
    return _one(
        conn,
        Draft,
        "SELECT * FROM drafts WHERE inquiry_id = ? ORDER BY version DESC LIMIT 1",
        (inquiry_id,),
    )


def list_drafts(conn: sqlite3.Connection, inquiry_id: int) -> list[Draft]:
    return _many(
        conn, Draft, "SELECT * FROM drafts WHERE inquiry_id = ? ORDER BY version", (inquiry_id,)
    )


def blocking_failures(conn: sqlite3.Connection, draft_id: int) -> list[CheckCode]:
    rows = conn.execute(
        "SELECT check_code FROM draft_checks WHERE draft_id = ? AND blocking = 1 AND passed = 0 "
        "ORDER BY id",
        (draft_id,),
    ).fetchall()
    return [CheckCode(r["check_code"]) for r in rows]


def set_draft_status(conn: sqlite3.Connection, draft_id: int, status: DraftStatus | str) -> None:
    new_status = DraftStatus(status)
    if new_status in (DraftStatus.ready, DraftStatus.approved):
        failed = blocking_failures(conn, draft_id)
        if failed:
            codes = ", ".join(c.value for c in failed)
            raise DraftBlocked(f"draft {draft_id} failed blocking check(s): {codes}")
    cursor = conn.execute("UPDATE drafts SET status = ? WHERE id = ?", (new_status.value, draft_id))
    if cursor.rowcount == 0:
        raise LookupError(f"no draft {draft_id}")


def supersede_older_drafts(conn: sqlite3.Connection, inquiry_id: int, *, keep_id: int) -> int:
    cursor = conn.execute(
        "UPDATE drafts SET status = 'superseded' "
        "WHERE inquiry_id = ? AND id != ? AND status IN ('ready', 'blocked')",
        (inquiry_id, keep_id),
    )
    return cursor.rowcount


def upsert_draft_check(
    conn: sqlite3.Connection,
    *,
    draft_id: int,
    check_code: CheckCode | str,
    blocking: bool,
    passed: bool,
    detail: dict[str, Any] | None = None,
    now: str | None = None,
) -> int:
    cursor = conn.execute(
        "INSERT INTO draft_checks (draft_id, check_code, blocking, passed, detail, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(draft_id, check_code) DO UPDATE SET blocking = excluded.blocking, "
        "passed = excluded.passed, detail = excluded.detail, created_at = excluded.created_at "
        "RETURNING id",
        (
            draft_id,
            CheckCode(check_code).value,
            int(blocking),
            int(passed),
            None if detail is None else json.dumps(detail),
            _now(now),
        ),
    )
    return _returning_id(cursor)


def list_draft_checks(conn: sqlite3.Connection, draft_id: int) -> list[DraftCheck]:
    return _many(
        conn, DraftCheck, "SELECT * FROM draft_checks WHERE draft_id = ? ORDER BY id", (draft_id,)
    )


# --- reviews and exports ---------------------------------------------------------------------


def insert_review(
    conn: sqlite3.Connection,
    *,
    inquiry_id: int,
    decision: Decision | str,
    draft_id: int | None = None,
    edited_body: str | None = None,
    reason: str | None = None,
    reviewer: str = "local",
    review_seconds: int | None = None,
    now: str | None = None,
) -> int:
    cursor = conn.execute(
        "INSERT INTO reviews (inquiry_id, draft_id, decision, edited_body, reason, reviewer, "
        "review_seconds, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            inquiry_id,
            draft_id,
            Decision(decision).value,
            edited_body,
            reason,
            reviewer,
            review_seconds,
            _now(now),
        ),
    )
    return _last_id(cursor)


def list_reviews(conn: sqlite3.Connection, inquiry_id: int) -> list[Review]:
    return _many(
        conn,
        Review,
        "SELECT * FROM reviews WHERE inquiry_id = ? ORDER BY created_at, id",
        (inquiry_id,),
    )


def decision_counts(conn: sqlite3.Connection) -> dict[Decision, int]:
    rows = conn.execute("SELECT decision, COUNT(*) AS n FROM reviews GROUP BY decision").fetchall()
    return {Decision(r["decision"]): int(r["n"]) for r in rows}


def approval_review_seconds(conn: sqlite3.Connection) -> list[int]:
    """Review times for approvals; the median is computed by the caller (SQLite has none)."""
    rows = conn.execute(
        "SELECT review_seconds FROM reviews "
        "WHERE decision IN ('approve', 'edit_approve') AND review_seconds IS NOT NULL"
    ).fetchall()
    return [int(r["review_seconds"]) for r in rows]


def insert_export(
    conn: sqlite3.Connection,
    *,
    draft_id: int,
    method: ExportMethod | str,
    external_ref: str | None = None,
    now: str | None = None,
) -> int:
    """Record that approved text was copied or saved as a mail draft. Nothing here sends."""
    cursor = conn.execute(
        "INSERT INTO exports (draft_id, method, external_ref, created_at) VALUES (?, ?, ?, ?)",
        (draft_id, ExportMethod(method).value, external_ref, _now(now)),
    )
    return _last_id(cursor)


def list_exports(conn: sqlite3.Connection, draft_id: int) -> list[Export]:
    return _many(conn, Export, "SELECT * FROM exports WHERE draft_id = ? ORDER BY id", (draft_id,))


# --- settings --------------------------------------------------------------------------------


def get_setting(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return None if row is None else cast(str, row["value"])


def set_setting(conn: sqlite3.Connection, key: str, value: str, *, now: str | None = None) -> None:
    conn.execute(
        "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
        (key, value, _now(now)),
    )
