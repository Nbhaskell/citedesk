"""Phase 8: logs and events hold no message or draft text (rule 4 in docs/RULES.md, TRD section 8).

Every message here carries odd words that cannot appear by chance. After the system has read,
drafted, failed and crashed on them, none may be found in a log record, in a traceback attached to
one, or in the audit events.
"""

import ast
import logging
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from citedesk import __main__ as entry
from citedesk import api, pipeline
from citedesk.api import create_app
from citedesk.business import Business
from citedesk.config import Settings
from citedesk.db import connect, migrate
from citedesk.intake import NewInquiry, submit
from citedesk.knowledge import FakeKB, KnowledgeBaseError
from citedesk.models import InquiryStatus
from citedesk.providers import FakeLLM
from tests.helpers import model_reply

S = InquiryStatus
PACKAGE = Path(__file__).resolve().parent.parent / "citedesk"
NOW = "2026-10-28T12:00:00Z"
BUSINESS = Business("Kestrel Hollow Plumbing", "555-0171", "555-0172", "kestrelhollow@example.com")
PRICE_PASSAGE = "Drain cleaning, one fixture (sink, tub, shower or toilet): $149 (starting price)"

# Words from the customer's message, the model's replies and the draft. None may reach a log.
MARKERS = ("zebediah", "quillfeather", "wobbly", "thistle", "periwinkle", "marmalade")
BODY = "Hello, Zebediah Quillfeather here. My wobbly thistle pipe leaks. How much to clear a drain?"
DRAFT: dict[str, Any] = {
    "subject": "Re: Thistle drain",
    "body": "Hi Zebediah,\n\nDrain cleaning for one fixture starts at $149 (periwinkle). A member "
    "of our team will confirm a visit time with you.\n\nKind regards,\nKestrel Hollow Plumbing",
    "claims": [{"text": "starts at $149", "source_index": 0}],
}


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = connect(":memory:")
    migrate(c)
    return c


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)


def store(conn: sqlite3.Connection, settings: Settings, **fields: Any) -> int:
    base: dict[str, Any] = {
        "sender_name": "Zebediah Quillfeather",
        "sender_email": "zebediah.quillfeather@example.com",
        "subject": "Thistle drain",
        "body": BODY,
        "received_at": NOW,
    }
    return submit(conn, NewInquiry.model_validate({**base, **fields}), settings, now=NOW).id


def answering() -> FakeKB:
    return FakeKB(
        lambda q: FakeKB.answered("It starts at $149.", ["pricing.md"], text=PRICE_PASSAGE)
    )


def everything_logged(caplog: pytest.LogCaptureFixture) -> str:
    """All the text of every record: message, arguments, and any traceback."""
    parts: list[str] = []
    for record in caplog.records:
        parts += [record.getMessage(), str(record.args), record.exc_text or ""]
        if record.exc_info:
            parts.append(repr(record.exc_info[1]))
    return "\n".join(parts).lower()


def audit_text(conn: sqlite3.Connection) -> str:
    rows = conn.execute("SELECT * FROM audit_events").fetchall()
    return "\n".join(" ".join(str(value) for value in tuple(row)) for row in rows).lower()


def no_markers(text: str) -> None:
    found = [word for word in MARKERS if word in text]
    assert not found, f"message or draft text reached a log or event: {found}"


# --- logs and events during a run ------------------------------------------------------------


def test_a_full_run_logs_and_records_no_message_or_draft_text(
    conn: sqlite3.Connection, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    inquiry_id = store(conn, settings)
    llm = FakeLLM([model_reply(summary="Thistle pipe, Zebediah asks a price."), DRAFT])
    pipeline.process(conn, inquiry_id, settings, llm=llm, kb=answering(), business=BUSINESS)
    assert {r.levelno for r in caplog.records} <= {logging.DEBUG, logging.INFO}
    no_markers(everything_logged(caplog))
    no_markers(audit_text(conn))


def test_failures_log_the_kind_of_failure_and_never_the_text(
    conn: sqlite3.Connection,
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    caplog.set_level(logging.DEBUG)

    # a model that answers with the customer's words and not JSON, twice
    first = store(conn, settings)
    llm = FakeLLM(["thistle marmalade nope", "wobbly marmalade nope"])
    assert pipeline.process(conn, first, settings, llm=llm) is S.failed

    # a knowledge base whose error message repeats the question
    second = store(conn, settings, subject="Another", body="Zebediah asks about a wobbly drain.")
    kb = FakeKB([KnowledgeBaseError("unavailable", "could not answer: thistle marmalade")])
    llm = FakeLLM([model_reply()])
    assert pipeline.process(conn, second, settings, llm=llm, kb=kb, business=BUSINESS) is S.failed

    # a crash whose own message carries the text
    third = store(conn, settings, subject="Third", body="Quillfeather asks about thistle pipes.")

    def crash(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("quillfeather thistle marmalade")

    monkeypatch.setattr(pipeline, "route_stage", crash)
    assert pipeline.process(conn, third, settings, llm=FakeLLM([model_reply()])) is S.failed

    assert caplog.records, "the failures should be logged by kind"
    no_markers(everything_logged(caplog))
    no_markers(audit_text(conn))
    assert all(r.exc_info is None for r in caplog.records), "a traceback can carry text"


# --- the API ---------------------------------------------------------------------------------


def test_an_unexpected_error_is_answered_and_logged_by_type_and_never_reaches_the_server(
    api_settings: Settings, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If an exception left the app, the server would log it with its traceback and message."""
    caplog.set_level(logging.DEBUG)

    def boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("zebediah quillfeather thistle marmalade")

    monkeypatch.setattr(api.intake, "submit", boom)
    app = create_app(api_settings, start_worker=False)
    with TestClient(app, raise_server_exceptions=True) as client:
        response = client.post(
            "/api/inquiries", json={"sender_name": "A", "subject": "B", "body": BODY}
        )
    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "internal_error"
    assert error["request_id"] == response.headers["X-Request-ID"]
    text = everything_logged(caplog)
    assert "runtimeerror" in text
    no_markers(text)
    no_markers(response.text.lower())


def test_the_server_does_not_write_an_access_log(monkeypatch: pytest.MonkeyPatch) -> None:
    """An access log line holds the URL, and the search box puts typed text in the URL."""
    seen: dict[str, Any] = {}
    monkeypatch.setattr(entry.uvicorn, "run", lambda app, **kwargs: seen.update(kwargs))
    monkeypatch.setattr(entry.OllamaProvider, "from_settings", classmethod(lambda cls, s: None))
    entry.main()
    assert seen["host"] == "127.0.0.1"
    assert seen["access_log"] is False


# --- a guard on the logging calls themselves -------------------------------------------------

LOG_METHODS = {"debug", "info", "warning", "error", "critical"}
# The only things a log call may be given as arguments. Each is an id, a code or a type name.
ALLOWED_ARGUMENTS = {
    "type(error).__name__",
    "type(error.__cause__).__name__",
    "error.reason",
    "stage.value",
    "inquiry_id",
}


def logging_calls() -> list[tuple[str, ast.Call]]:
    found = []
    for path in sorted(PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text("utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in {"logger", "log", "logging"}
            ):
                found.append((f"{path.name}:{node.lineno}", node))
    return found


def test_the_package_logs_through_a_guarded_set_of_calls() -> None:
    calls = logging_calls()
    assert calls, "the guard found no logging calls; its pattern may be out of date"
    for where, call in calls:
        assert isinstance(call.func, ast.Attribute)
        method = call.func.attr
        assert method in LOG_METHODS or method == "getLogger", (
            f"{where}: logging.{method} can attach a traceback with the message in it"
        )
        if method == "getLogger":
            continue
        assert not call.keywords, f"{where}: logging options such as exc_info are not allowed"
        template, *arguments = call.args
        assert isinstance(template, ast.Constant) and isinstance(template.value, str), (
            f"{where}: the log message must be a fixed string; pass values as arguments"
        )
        for argument in arguments:
            assert ast.unparse(argument) in ALLOWED_ARGUMENTS, (
                f"{where}: {ast.unparse(argument)} is not an id, a code or a type name; if it "
                "is one, add it to ALLOWED_ARGUMENTS in this test"
            )


def test_nothing_in_the_package_prints_except_the_migration_command() -> None:
    for path in sorted(PACKAGE.rglob("*.py")):
        if path.name == "db.py":
            continue
        for node in ast.walk(ast.parse(path.read_text("utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id != "print", f"{path.name}:{node.lineno} prints"
