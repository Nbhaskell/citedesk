"""Deleting inquiries, one by a person or many by age (citedesk/retention.py, D-101)."""

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from citedesk import db, repo, retention, review
from citedesk.config import Settings
from citedesk.db import connect, migrate
from citedesk.models import AuditEventType, InquiryStatus
from citedesk.review import NotFound, WrongState
from tests.helpers import T1, in_review, walk

S = InquiryStatus
MARKER = "UNIQUE-MARKER-WORDS-91827"
CHILD_TABLES = (
    "screenings",
    "classifications",
    "extractions",
    "escalations",
    "retrievals",
    "drafts",
    "reviews",
)


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = connect(":memory:")
    migrate(c)
    return c


def exported(conn: sqlite3.Connection) -> tuple[int, int]:
    """An inquiry whose approved reply was copied: closed, with a review, an export and events."""
    inquiry_id, draft_id = in_review(conn)
    review.approve(conn, draft_id, now=T1)
    review.export(conn, draft_id, now=T1)
    return inquiry_id, draft_id


def rows_about(conn: sqlite3.Connection, inquiry_id: int, draft_id: int) -> dict[str, int]:
    counts = {
        table: conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE inquiry_id = ?",  # noqa: S608 (fixed names)
            (inquiry_id,),
        ).fetchone()[0]
        for table in (*CHILD_TABLES, "audit_events")
    }
    for table in ("draft_checks", "exports"):
        counts[table] = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE draft_id = ?",  # noqa: S608 (fixed names)
            (draft_id,),
        ).fetchone()[0]
    return counts


def test_deleting_removes_the_inquiry_and_everything_stored_about_it(
    conn: sqlite3.Connection,
) -> None:
    inquiry_id, draft_id = exported(conn)
    before = rows_about(conn, inquiry_id, draft_id)
    assert before["drafts"] and before["reviews"] and before["exports"] and before["audit_events"]
    result = retention.delete_inquiry(conn, inquiry_id, now=T1)
    assert result == retention.Deleted(inquiry_id, S.exported)
    assert repo.get_inquiry(conn, inquiry_id) is None
    assert all(n == 0 for n in rows_about(conn, inquiry_id, draft_id).values())


def test_one_event_without_text_is_left_in_its_place(conn: sqlite3.Connection) -> None:
    inquiry_id, _ = exported(conn)
    retention.delete_inquiry(conn, inquiry_id, request_id="req-1", now=T1)
    [event] = conn.execute("SELECT * FROM audit_events").fetchall()
    assert event["event_type"] == AuditEventType.inquiry_deleted
    assert event["inquiry_id"] is None and event["from_status"] == "exported"
    assert json.loads(event["payload"]) == {"deleted_inquiry_id": inquiry_id, "cause": "reviewer"}


@pytest.mark.parametrize("status", [S.received, S.screened, S.classified, S.routed, S.drafted])
def test_an_inquiry_the_worker_may_be_processing_is_not_deleted(
    conn: sqlite3.Connection, status: S
) -> None:
    inquiry_id = repo.insert_inquiry(conn, channel="web_form", body="Hi", now=T1)
    path = [S.screened, S.classified, S.routed, S.drafted]
    walk(conn, inquiry_id, *path[: path.index(status) + 1] if status in path else [])
    with pytest.raises(WrongState):
        retention.delete_inquiry(conn, inquiry_id)
    assert repo.get_inquiry(conn, inquiry_id) is not None


def test_a_missing_inquiry_is_not_found(conn: sqlite3.Connection) -> None:
    with pytest.raises(NotFound):
        retention.delete_inquiry(conn, 999)


def test_later_duplicates_stay_and_lose_their_link(conn: sqlite3.Connection) -> None:
    original, _ = exported(conn)
    later = repo.insert_inquiry(
        conn, channel="web_form", body="Again", duplicate_of=original, now=T1
    )
    retention.delete_inquiry(conn, original)
    kept = repo.get_inquiry(conn, later)
    assert kept is not None and kept.duplicate_of is None


def test_deleted_text_is_not_left_in_the_database_files(tmp_path: Path) -> None:
    path = tmp_path / "x.db"
    conn = connect(path)
    migrate(conn)
    inquiry_id = repo.insert_inquiry(
        conn, channel="web_form", body=f"Please call about {MARKER}", now=T1
    )
    walk(conn, inquiry_id, S.screened, S.archived)
    retention.checkpoint(conn)
    assert MARKER.encode() in path.read_bytes()
    retention.delete_inquiry(conn, inquiry_id)
    retention.checkpoint(conn)
    conn.close()
    for file in tmp_path.iterdir():
        assert MARKER.encode() not in file.read_bytes(), file.name


# --- purge by age ----------------------------------------------------------------------------


def aged(conn: sqlite3.Connection, inquiry_id: int, stamp: str) -> None:
    conn.execute("UPDATE inquiries SET updated_at = ? WHERE id = ?", (stamp, inquiry_id))


def test_only_closed_inquiries_older_than_the_period_expire(conn: sqlite3.Connection) -> None:
    old_closed, _ = exported(conn)
    new_closed, _ = exported(conn)
    old_open, _ = in_review(conn)
    aged(conn, old_closed, "2026-01-01T00:00:00Z")
    aged(conn, old_open, "2026-01-01T00:00:00Z")
    aged(conn, new_closed, "2026-10-30T00:00:00Z")
    now = "2026-11-01T00:00:00Z"
    assert retention.expired(conn, 30, now=now) == [old_closed]
    done = retention.purge(conn, 30, now=now)
    assert [d.inquiry_id for d in done] == [old_closed]
    assert repo.get_inquiry(conn, new_closed) is not None
    assert repo.get_inquiry(conn, old_open) is not None
    [event] = conn.execute(
        "SELECT payload FROM audit_events WHERE event_type = 'inquiry_deleted'"
    ).fetchall()
    assert json.loads(event["payload"])["cause"] == "retention"


def test_a_period_under_one_day_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValueError, match="at least"):
        retention.expired(conn, 0)


def test_the_purge_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "c.db"
    monkeypatch.setenv("CITEDESK_DB_PATH", str(path))
    assert db.main(["migrate"]) == 0
    conn = connect(path)
    inquiry_id, _ = exported(conn)
    aged(conn, inquiry_id, "2020-01-01T00:00:00Z")
    conn.close()

    assert db.main(["purge", "--older-than", "30", "--dry-run"]) == 0
    assert f"Would delete 1 closed inquiries older than 30 days: [{inquiry_id}]" in (
        capsys.readouterr().out
    )
    conn = connect(path)
    assert repo.get_inquiry(conn, inquiry_id) is not None
    conn.close()

    assert db.main(["purge", "--older-than", "30"]) == 0
    assert "Deleted 1 closed" in capsys.readouterr().out
    conn = connect(path)
    assert repo.get_inquiry(conn, inquiry_id) is None
    conn.close()

    assert db.main(["purge", "--older-than", "0"]) == 2
    assert db.main(["purge", "--older-than", "x"]) == 2
    assert db.main(["purge"]) == 2


# --- the API ---------------------------------------------------------------------------------


def test_delete_through_the_api(client: TestClient, api_settings: Settings) -> None:
    conn = connect(api_settings.db_path)
    inquiry_id, _ = in_review(conn)
    received = repo.insert_inquiry(conn, channel="web_form", body="Hi", now=T1)
    conn.close()

    response = client.delete(f"/api/inquiries/{inquiry_id}")
    assert response.status_code == 204 and response.content == b""
    assert client.get(f"/api/inquiries/{inquiry_id}").status_code == 404
    assert client.delete(f"/api/inquiries/{inquiry_id}").status_code == 404
    assert client.delete(f"/api/inquiries/{received}").status_code == 409


def test_another_site_cannot_delete(client: TestClient, api_settings: Settings) -> None:
    conn = connect(api_settings.db_path)
    inquiry_id, _ = in_review(conn)
    conn.close()
    response = client.delete(
        f"/api/inquiries/{inquiry_id}", headers={"Origin": "https://example.com"}
    )
    assert response.status_code == 403
    assert client.get(f"/api/inquiries/{inquiry_id}").status_code == 200
