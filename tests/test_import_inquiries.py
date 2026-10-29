import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest

from tools.import_inquiries import (
    InboxError,
    check_url,
    golden_to_inbox,
    import_inbox,
    main,
    post_record,
    read_jsonl,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN = json.loads((REPO_ROOT / "eval/golden/citedesk_v1.json").read_text("utf-8"))


def record(**over: Any) -> dict[str, Any]:
    base = {
        "external_id": "a-1",
        "channel": "web_form",
        "sender_name": "Alex Rivera",
        "sender_email": "alex.rivera@example.com",
        "subject": "hello",
        "body": "How much to clear a drain?",
    }
    return {**base, **over}


# --- converting the golden set to an inbox ---------------------------------------------------


TUNED = [i for i in GOLDEN["items"] if i["split"] == "tuned"]
HELDOUT = [i for i in GOLDEN["items"] if i["split"] == "heldout"]


def test_every_golden_item_becomes_one_record() -> None:
    inbox = golden_to_inbox(GOLDEN, split="tuned")
    assert len(inbox) == len(TUNED)
    assert [r["external_id"] for r in inbox] == [i["id"] for i in TUNED]


def test_labels_and_hints_never_leave_the_golden_file() -> None:
    forbidden = {"labels", "notes", "category", "evidence", "split", "id"}
    for rec in golden_to_inbox(GOLDEN, split="tuned"):
        assert not forbidden & set(rec), rec
        assert set(rec) <= {
            "external_id",
            "channel",
            "sender_name",
            "sender_email",
            "subject",
            "body",
        }


def test_no_note_text_leaks_into_any_record() -> None:
    blob = json.dumps(golden_to_inbox(GOLDEN, split="all"))
    for item in GOLDEN["items"]:
        if item.get("notes"):
            assert item["notes"] not in blob


def test_split_filter() -> None:
    assert [r["external_id"] for r in golden_to_inbox(GOLDEN, split="heldout")] == [
        i["id"] for i in HELDOUT
    ]
    assert len(golden_to_inbox(GOLDEN, split="all")) == len(GOLDEN["items"])
    assert len(TUNED) + len(HELDOUT) == len(GOLDEN["items"])


def test_missing_optional_fields_are_omitted_not_null() -> None:
    data = {
        "items": [
            {
                "id": "x",
                "split": "tuned",
                "channel": "email",
                "sender_name": "A B",
                "sender_email": None,
                "subject": None,
                "body": "hi",
            }
        ]
    }
    assert golden_to_inbox(data, split="all") == [
        {"external_id": "x", "channel": "email", "sender_name": "A B", "body": "hi"}
    ]


# --- reading a JSONL inbox -------------------------------------------------------------------


def write_lines(tmp_path: Path, lines: list[str]) -> Path:
    path = tmp_path / "inbox.jsonl"
    path.write_text("\n".join(lines) + "\n", "utf-8")
    return path


def test_read_jsonl_reads_valid_lines_and_skips_blank_ones(tmp_path: Path) -> None:
    path = write_lines(tmp_path, [json.dumps(record()), "", json.dumps(record(external_id="a-2"))])
    assert [r["external_id"] for r in read_jsonl(path)] == ["a-1", "a-2"]


@pytest.mark.parametrize(
    ("line", "needle"),
    [
        ("{not json", "line 1"),
        (json.dumps(record(channel="carrier_pigeon")), "channel"),
        (json.dumps(record(body="")), "body"),
        (json.dumps({k: v for k, v in record().items() if k != "external_id"}), "external_id"),
        (json.dumps(record(labels={"primary_intent": "spam"})), "labels"),
        (json.dumps([1, 2]), "object"),
    ],
)
def test_read_jsonl_rejects_bad_lines(tmp_path: Path, line: str, needle: str) -> None:
    with pytest.raises(InboxError, match=needle):
        read_jsonl(write_lines(tmp_path, [line]))


def test_read_jsonl_reports_the_line_number(tmp_path: Path) -> None:
    path = write_lines(tmp_path, [json.dumps(record()), json.dumps(record(body=""))])
    with pytest.raises(InboxError, match="line 2"):
        read_jsonl(path)


def test_duplicate_external_ids_in_one_file_are_rejected(tmp_path: Path) -> None:
    path = write_lines(tmp_path, [json.dumps(record()), json.dumps(record())])
    with pytest.raises(InboxError, match="duplicate"):
        read_jsonl(path)


# --- where it may send ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "url", ["http://127.0.0.1:8100", "http://localhost:8100", "http://[::1]:8100"]
)
def test_loopback_urls_are_allowed(url: str) -> None:
    check_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "http://192.168.1.5:8100",
        "http://0.0.0.0:8100",
        "https://127.0.0.1:8100",
        "ftp://127.0.0.1",
        "127.0.0.1:8100",
        "http://127.0.0.1.evil.test",
    ],
)
def test_other_urls_are_refused(url: str) -> None:
    with pytest.raises(InboxError):
        check_url(url)


# --- importing ------------------------------------------------------------------------------


def test_import_counts_created_duplicates_and_failures() -> None:
    recs = [record(external_id=f"r-{i}") for i in range(4)]
    codes = {"r-0": 201, "r-1": 409, "r-2": 500, "r-3": 201}
    result = import_inbox(recs, lambda r: codes[r["external_id"]])
    assert (result.created, result.duplicates) == (2, 1)
    assert result.failed == ["r-2"]


def test_import_keeps_going_after_a_failure() -> None:
    seen: list[str] = []

    def post(r: dict[str, Any]) -> int:
        seen.append(r["external_id"])
        return 500 if r["external_id"] == "r-0" else 201

    import_inbox([record(external_id="r-0"), record(external_id="r-1")], post)
    assert seen == ["r-0", "r-1"]


def test_connection_failure_counts_as_a_failure() -> None:
    result = import_inbox([record()], lambda r: 0)
    assert result.failed == ["a-1"]


def test_dry_run_posts_nothing() -> None:
    def post(r: dict[str, Any]) -> int:
        raise AssertionError("must not post in a dry run")

    result = import_inbox([record(), record(external_id="a-2")], post, dry_run=True)
    assert result.created == 0 and result.would_import == 2


def test_limit() -> None:
    seen: list[str] = []
    import_inbox(
        [record(external_id=f"r-{i}") for i in range(5)],
        lambda r: seen.append(r["external_id"]) or 201,
        limit=2,
    )
    assert seen == ["r-0", "r-1"]


def test_main_prints_ids_and_counts_but_never_message_text(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    message_text = "my card is 4111 1111 1111 1111 and my cat is called Biscuit"
    path = write_lines(tmp_path, [json.dumps(record(body=message_text))])
    code = main(["--source", str(path), "--dry-run"])
    out = capsys.readouterr()
    assert code == 0
    assert message_text not in out.out + out.err
    assert "Biscuit" not in out.out + out.err
    assert "1" in out.out


def test_main_refuses_a_non_loopback_url(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--url", "http://example.com"]) == 2
    assert "loopback" in capsys.readouterr().err.lower()


# --- the real HTTP call, against a stand-in server on loopback -------------------------------


class Handler(BaseHTTPRequestHandler):
    received: list[dict[str, Any]] = []
    status_for: dict[str, int] = {}

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers["Content-Length"])
        body = json.loads(self.rfile.read(length))
        Handler.received.append(
            {"path": self.path, "type": self.headers["Content-Type"], "body": body}
        )
        self.send_response(Handler.status_for.get(body["external_id"], 201))
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass


@pytest.fixture
def server() -> Iterator[str]:
    Handler.received = []
    Handler.status_for = {"dup": 409, "boom": 500}
    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    thread.join()


def test_post_record_sends_json_to_the_inquiries_endpoint(server: str) -> None:
    assert post_record(server, record()) == 201
    sent = Handler.received[0]
    assert sent["path"] == "/api/inquiries"
    assert sent["type"] == "application/json"
    assert sent["body"] == record()


def test_post_record_returns_the_http_status_for_errors(server: str) -> None:
    assert post_record(server, record(external_id="dup")) == 409
    assert post_record(server, record(external_id="boom")) == 500


def test_post_record_returns_zero_when_nothing_is_listening() -> None:
    assert post_record("http://127.0.0.1:9", record(), timeout=1) == 0


def test_end_to_end_through_main(server: str, tmp_path: Path) -> None:
    path = write_lines(tmp_path, [json.dumps(record(external_id=x)) for x in ("ok", "dup", "boom")])
    assert main(["--source", str(path), "--url", server]) == 1
    assert len(Handler.received) == 3
