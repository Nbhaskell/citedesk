import re
import sqlite3
from pathlib import Path

import pytest

from citedesk import db
from citedesk.db import MigrationError, connect, migrate

REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_MIGRATIONS = REPO_ROOT / "db/migrations"

EXPECTED_TABLES = {
    "schema_migrations",
    "inquiries",
    "screenings",
    "classifications",
    "extractions",
    "escalations",
    "retrievals",
    "drafts",
    "draft_checks",
    "reviews",
    "exports",
    "audit_events",
    "settings",
}

TRACKER_DDL = """
CREATE TABLE schema_migrations (
  version     INTEGER PRIMARY KEY,
  name        TEXT NOT NULL,
  applied_at  TEXT NOT NULL
);
"""


def tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {r["name"] for r in rows if not r["name"].startswith("sqlite_")}


def write_migrations(directory: Path, files: dict[str, str]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    for name, sql in files.items():
        (directory / name).write_text(sql, "utf-8")
    return directory


@pytest.fixture
def conn() -> sqlite3.Connection:
    return connect(":memory:")


def insert_inquiry(conn: sqlite3.Connection, **over: object) -> int:
    values = {
        "channel": "web_form",
        "received_at": "2026-10-28T10:00:00Z",
        "body": "hello",
        "created_at": "2026-10-28T10:00:00Z",
        "updated_at": "2026-10-28T10:00:00Z",
        **over,
    }
    cols = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    sql = f"INSERT INTO inquiries ({cols}) VALUES ({marks})"  # noqa: S608 (column names are literals)
    cur = conn.execute(sql, tuple(values.values()))
    assert cur.lastrowid is not None
    return cur.lastrowid


# --- connection ------------------------------------------------------------------------------


def test_connect_turns_foreign_keys_on_and_returns_rows(conn: sqlite3.Connection) -> None:
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.execute("SELECT 1 AS one").fetchone()["one"] == 1


def test_file_databases_use_wal(tmp_path: Path) -> None:
    file_conn = connect(tmp_path / "x.db")
    assert file_conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    file_conn.close()


def test_utc_now_is_iso_8601_utc() -> None:
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", db.utc_now())


# --- the real migration ----------------------------------------------------------------------


def test_all_migrations_apply_to_an_empty_database(conn: sqlite3.Connection) -> None:
    assert migrate(conn, REAL_MIGRATIONS) == [1, 2]
    assert tables(conn) == EXPECTED_TABLES


def test_the_applied_migration_is_recorded(conn: sqlite3.Connection) -> None:
    migrate(conn, REAL_MIGRATIONS)
    row = conn.execute("SELECT * FROM schema_migrations ORDER BY version").fetchone()
    assert (row["version"], row["name"]) == (1, "init")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", row["applied_at"])


def test_migrating_twice_applies_nothing_the_second_time(conn: sqlite3.Connection) -> None:
    migrate(conn, REAL_MIGRATIONS)
    assert migrate(conn, REAL_MIGRATIONS) == []
    assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 2


def test_migration_file_is_exactly_the_sql_in_the_schema_document() -> None:
    doc = (REPO_ROOT / "docs/BACKEND_SCHEMA.md").read_text("utf-8")
    section = doc.split("## 3. Tables", 1)[1].split("## 4.", 1)[0]
    block = re.search(r"```sql\n(.*?)```", section, flags=re.DOTALL)
    assert block, "no SQL block found in section 3 of BACKEND_SCHEMA.md"
    on_disk = (REAL_MIGRATIONS / "0001_init.sql").read_text("utf-8")
    assert on_disk == block.group(1)


# --- the schema behaves as documented --------------------------------------------------------


def test_foreign_keys_are_enforced(conn: sqlite3.Connection) -> None:
    migrate(conn, REAL_MIGRATIONS)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO screenings (inquiry_id, spam_score, result, created_at) "
            "VALUES (999, 0.1, 'clean', 'x')"
        )


def test_check_constraints_reject_unknown_values(conn: sqlite3.Connection) -> None:
    migrate(conn, REAL_MIGRATIONS)
    with pytest.raises(sqlite3.IntegrityError):
        insert_inquiry(conn, status="bogus")
    with pytest.raises(sqlite3.IntegrityError):
        insert_inquiry(conn, channel="carrier_pigeon")


def test_new_inquiries_default_to_received_and_synthetic(conn: sqlite3.Connection) -> None:
    migrate(conn, REAL_MIGRATIONS)
    row = conn.execute("SELECT * FROM inquiries WHERE id = ?", (insert_inquiry(conn),)).fetchone()
    assert (row["status"], row["is_synthetic"]) == ("received", 1)


def test_external_id_is_unique_per_channel_but_null_is_free(conn: sqlite3.Connection) -> None:
    migrate(conn, REAL_MIGRATIONS)
    insert_inquiry(conn, external_id="a-1")
    insert_inquiry(conn, external_id="a-1", channel="email")
    insert_inquiry(conn)
    insert_inquiry(conn)
    with pytest.raises(sqlite3.IntegrityError):
        insert_inquiry(conn, external_id="a-1")


def test_deleting_an_inquiry_cascades_to_its_children(conn: sqlite3.Connection) -> None:
    migrate(conn, REAL_MIGRATIONS)
    inquiry_id = insert_inquiry(conn)
    conn.execute(
        "INSERT INTO screenings (inquiry_id, spam_score, result, created_at) "
        "VALUES (?, 0.1, 'clean', 'x')",
        (inquiry_id,),
    )
    conn.execute("DELETE FROM inquiries WHERE id = ?", (inquiry_id,))
    assert conn.execute("SELECT COUNT(*) FROM screenings").fetchone()[0] == 0


def test_a_draft_version_is_unique_per_inquiry(conn: sqlite3.Connection) -> None:
    migrate(conn, REAL_MIGRATIONS)
    inquiry_id = insert_inquiry(conn)
    sql = (
        "INSERT INTO drafts (inquiry_id, version, kind, body, model, prompt_version, created_at) "
        "VALUES (?, 1, 'reply', 'b', 'm', 'p', 'x')"
    )
    conn.execute(sql, (inquiry_id,))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(sql, (inquiry_id,))


# --- the runner's rules ----------------------------------------------------------------------


def test_only_pending_migrations_are_applied(conn: sqlite3.Connection, tmp_path: Path) -> None:
    directory = write_migrations(
        tmp_path / "m", {"0001_first.sql": TRACKER_DDL + "CREATE TABLE a (x);"}
    )
    assert migrate(conn, directory) == [1]
    write_migrations(directory, {"0002_second.sql": "CREATE TABLE b (x);"})
    assert migrate(conn, directory) == [2]
    assert {"a", "b"} <= tables(conn)


def test_a_failing_migration_is_rolled_back_completely(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    directory = write_migrations(
        tmp_path / "m",
        {
            "0001_first.sql": TRACKER_DDL + "CREATE TABLE a (x);",
            "0002_broken.sql": "CREATE TABLE b (x);\nINSERT INTO does_not_exist VALUES (1);",
        },
    )
    with pytest.raises(MigrationError, match="0002"):
        migrate(conn, directory)
    assert "b" not in tables(conn)
    assert [r["version"] for r in conn.execute("SELECT version FROM schema_migrations")] == [1]
    assert not conn.in_transaction


def test_gaps_in_the_numbering_are_refused(conn: sqlite3.Connection, tmp_path: Path) -> None:
    directory = write_migrations(
        tmp_path / "m", {"0001_a.sql": TRACKER_DDL, "0003_c.sql": "CREATE TABLE c (x);"}
    )
    with pytest.raises(MigrationError, match="gap|missing|0002"):
        migrate(conn, directory)
    assert tables(conn) == set()


def test_duplicate_version_numbers_are_refused(conn: sqlite3.Connection, tmp_path: Path) -> None:
    directory = write_migrations(
        tmp_path / "m", {"0001_a.sql": TRACKER_DDL, "0001_b.sql": "CREATE TABLE b (x);"}
    )
    with pytest.raises(MigrationError, match="duplicate"):
        migrate(conn, directory)


@pytest.mark.parametrize("name", ["init.sql", "1_init.sql", "0001-init.sql", "0001_Init.sql"])
def test_badly_named_files_are_refused(conn: sqlite3.Connection, tmp_path: Path, name: str) -> None:
    directory = write_migrations(tmp_path / "m", {name: "SELECT 1;"})
    with pytest.raises(MigrationError, match="name"):
        migrate(conn, directory)


def test_a_database_newer_than_the_code_is_refused(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    directory = write_migrations(
        tmp_path / "m",
        {"0001_a.sql": TRACKER_DDL, "0002_b.sql": "CREATE TABLE b (x);"},
    )
    migrate(conn, directory)
    older = write_migrations(tmp_path / "older", {"0001_a.sql": TRACKER_DDL})
    with pytest.raises(MigrationError, match="newer|unknown"):
        migrate(conn, older)


def test_non_sql_files_in_the_folder_are_ignored(conn: sqlite3.Connection, tmp_path: Path) -> None:
    directory = write_migrations(
        tmp_path / "m", {"0001_a.sql": TRACKER_DDL, ".gitkeep": "", "notes.txt": "x"}
    )
    assert migrate(conn, directory) == [1]


def test_an_empty_folder_applies_nothing(conn: sqlite3.Connection, tmp_path: Path) -> None:
    (tmp_path / "m").mkdir()
    assert migrate(conn, tmp_path / "m") == []


# --- the command line ------------------------------------------------------------------------


def test_cli_migrate_creates_the_database_and_its_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "data" / "citedesk.db"
    monkeypatch.setenv("CITEDESK_DB_PATH", str(target))
    assert db.main(["migrate"]) == 0
    assert target.exists()
    assert "1" in capsys.readouterr().out
    again = connect(target)
    assert tables(again) == EXPECTED_TABLES
    again.close()


def test_cli_migrate_twice_reports_up_to_date(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CITEDESK_DB_PATH", str(tmp_path / "citedesk.db"))
    db.main(["migrate"])
    capsys.readouterr()
    assert db.main(["migrate"]) == 0
    assert "up to date" in capsys.readouterr().out


def test_cli_without_a_command_exits_with_usage(capsys: pytest.CaptureFixture[str]) -> None:
    assert db.main([]) == 2
