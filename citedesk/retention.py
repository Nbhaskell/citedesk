"""Deleting inquiries: one at a time by a person, or in bulk by age (D-101).

Deleting an inquiry removes it and everything stored about it (screening, reading, extraction,
escalations, retrievals, drafts and their checks, reviews, exports and its audit events) through
the `ON DELETE CASCADE` foreign keys. One audit event is written in its place, with no inquiry id
column, holding only the deleted id and its last status (rule 4: ids and codes, never text).

An inquiry the worker may still be processing (`received` to `drafted`) cannot be deleted: the
worker would fail on a row that disappeared under it. Once it has stopped, it can.

Connections use `PRAGMA secure_delete` (citedesk/db.py), so deleted text is overwritten in the
database file, and the write-ahead log is checkpointed after a delete so old pages do not linger
there. Backups and copies of the file are outside this code's reach.

    python -m citedesk.db purge --older-than DAYS [--dry-run]

deletes closed inquiries (`exported`, `resolved`, `archived`) not changed for DAYS days.
"""

import contextlib
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from citedesk import events, repo
from citedesk.db import transaction, utc_now
from citedesk.models import AuditEventType, InquiryStatus
from citedesk.review import NotFound, WrongState

S = InquiryStatus

IN_FLIGHT: frozenset[InquiryStatus] = frozenset(
    {S.received, S.screened, S.classified, S.routed, S.drafted}
)
CLOSED: tuple[InquiryStatus, ...] = (S.exported, S.resolved, S.archived)
MIN_RETENTION_DAYS = 1


@dataclass(frozen=True)
class Deleted:
    inquiry_id: int
    status: InquiryStatus


def checkpoint(conn: sqlite3.Connection) -> None:
    """Fold the write-ahead log into the database file and empty it, if no reader blocks it.
    Best effort: a busy log is folded in at the next checkpoint instead."""
    with contextlib.suppress(sqlite3.OperationalError):
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")


def delete_inquiry(
    conn: sqlite3.Connection,
    inquiry_id: int,
    *,
    cause: str = "reviewer",
    request_id: str | None = None,
    now: str | None = None,
) -> Deleted:
    """Delete one inquiry and everything stored about it. Raises NotFound or WrongState."""
    with transaction(conn):
        inquiry = repo.get_inquiry(conn, inquiry_id)
        if inquiry is None:
            raise NotFound("No inquiry has that id.")
        if inquiry.status in IN_FLIGHT:
            raise WrongState(
                "This inquiry is still being processed. Try again when it has stopped."
            )
        # Later messages may point at this one as their original; they stay, unlinked.
        conn.execute(
            "UPDATE inquiries SET duplicate_of = NULL WHERE duplicate_of = ?", (inquiry_id,)
        )
        conn.execute("DELETE FROM inquiries WHERE id = ?", (inquiry_id,))
        events.record_event(
            conn,
            event_type=AuditEventType.inquiry_deleted,
            from_status=inquiry.status,
            payload={"deleted_inquiry_id": inquiry_id, "cause": cause},
            request_id=request_id,
            now=now,
        )
    return Deleted(inquiry_id, inquiry.status)


def _cutoff(older_than_days: int, now: str | None) -> str:
    moment = datetime.now(UTC) if now is None else datetime.fromisoformat(now)
    return (moment - timedelta(days=older_than_days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def expired(conn: sqlite3.Connection, older_than_days: int, *, now: str | None = None) -> list[int]:
    """Ids of closed inquiries last changed more than `older_than_days` days ago."""
    if older_than_days < MIN_RETENTION_DAYS:
        raise ValueError(f"the retention period must be at least {MIN_RETENTION_DAYS} day")
    marks = ", ".join("?" for _ in CLOSED)
    rows = conn.execute(
        f"SELECT id FROM inquiries WHERE status IN ({marks}) AND updated_at < ? ORDER BY id",  # noqa: S608
        (*[s.value for s in CLOSED], _cutoff(older_than_days, now)),
    ).fetchall()
    return [int(r["id"]) for r in rows]


def purge(
    conn: sqlite3.Connection, older_than_days: int, *, now: str | None = None
) -> list[Deleted]:
    """Delete every expired inquiry, each in its own transaction, then checkpoint the log."""
    stamp = now or utc_now()
    done = [
        delete_inquiry(conn, inquiry_id, cause="retention", now=stamp)
        for inquiry_id in expired(conn, older_than_days, now=stamp)
    ]
    checkpoint(conn)
    return done
