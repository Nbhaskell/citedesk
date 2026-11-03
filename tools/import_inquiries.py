"""Load an inbox of inquiries into the running API.

Run (the API must be listening; see the README for how to start it):
    python -m tools.import_inquiries                      the tuned golden set, to 127.0.0.1:8100
    python -m tools.import_inquiries --dry-run            validate and count, send nothing
    python -m tools.import_inquiries --source inbox.jsonl any JSONL inbox, one object per line
    python -m tools.import_inquiries --split heldout      only after the held-out set is written

Each record is posted to POST /api/inquiries as JSON with these fields only: external_id, channel,
sender_name, sender_email (optional), subject (optional), body. Labels, notes, categories and
evidence never leave the golden file, so the system under test is not given the answers.

A 409 answer means the inquiry was already imported. The tool refuses any address that is not
loopback, and prints ids and counts only, never message text.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from tools.golden import GOLDEN_FILE, REPO_ROOT, schema_enum

REQUIRED = ("external_id", "channel", "sender_name", "body")
OPTIONAL = ("sender_email", "subject")
LOOPBACK = {"127.0.0.1", "localhost", "::1"}
DEFAULT_URL = "http://127.0.0.1:8100"
ENDPOINT = "/api/inquiries"


class InboxError(Exception):
    """Something is wrong with the inbox or the target; the message is safe to print."""


def check_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "http" or parsed.hostname not in LOOPBACK:
        raise InboxError(
            f"refusing to send to {url!r}: only loopback addresses "
            "(http://127.0.0.1, http://localhost, http://[::1]) are allowed"
        )


def golden_to_inbox(data: dict[str, Any], *, split: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in data["items"]:
        if split != "all" and item["split"] != split:
            continue
        rec: dict[str, Any] = {
            "external_id": item["id"],
            "channel": item["channel"],
            "sender_name": item["sender_name"],
            "body": item["body"],
        }
        for key in OPTIONAL:
            if item.get(key) is not None:
                rec[key] = item[key]
        records.append(dict(sorted(rec.items(), key=lambda kv: (kv[0] != "external_id", kv[0]))))
    return records


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    channels = set(schema_enum("channel"))
    allowed = set(REQUIRED) | set(OPTIONAL)
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for number, line in enumerate(path.read_text("utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as error:
            raise InboxError(f"line {number}: not valid JSON ({error.msg})") from error
        if not isinstance(rec, dict):
            raise InboxError(f"line {number}: must be a JSON object")
        unknown = sorted(set(rec) - allowed)
        if unknown:
            raise InboxError(f"line {number}: unknown field(s) {unknown}")
        for key in REQUIRED:
            if not isinstance(rec.get(key), str) or not rec[key].strip():
                raise InboxError(f"line {number}: {key} is missing or empty")
        for key in OPTIONAL:
            if key in rec and not isinstance(rec[key], str):
                raise InboxError(f"line {number}: {key} must be a string")
        if rec["channel"] not in channels:
            raise InboxError(
                f"line {number}: channel {rec['channel']!r} is not one of {sorted(channels)}"
            )
        if rec["external_id"] in seen:
            raise InboxError(f"line {number}: duplicate external_id {rec['external_id']!r}")
        seen.add(rec["external_id"])
        records.append(rec)
    return records


@dataclass
class Result:
    created: int = 0
    duplicates: int = 0
    would_import: int = 0
    failed: list[str] = field(default_factory=list)


def import_inbox(
    records: list[dict[str, Any]],
    post: Callable[[dict[str, Any]], int],
    *,
    dry_run: bool = False,
    limit: int | None = None,
) -> Result:
    result = Result()
    for rec in records[:limit]:
        if dry_run:
            result.would_import += 1
            continue
        status = post(rec)
        if status in (200, 201):
            result.created += 1
        elif status == 409:
            result.duplicates += 1
        else:
            result.failed.append(rec["external_id"])
    return result


def post_record(base_url: str, rec: dict[str, Any], timeout: float = 10) -> int:
    """POST one record and return the HTTP status, or 0 if the server cannot be reached."""
    check_url(base_url)
    request = urllib.request.Request(  # noqa: S310  (scheme and host are checked above)
        base_url.rstrip("/") + ENDPOINT,
        data=json.dumps(rec).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return int(response.status)
    except urllib.error.HTTPError as error:
        error.close()
        return error.code
    except (urllib.error.URLError, OSError):
        return 0


def load_source(source: Path, split: str) -> list[dict[str, Any]]:
    if source.suffix == ".jsonl":
        return read_jsonl(source)
    return golden_to_inbox(json.loads(source.read_text("utf-8")), split=split)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.import_inquiries", description=__doc__)
    parser.add_argument(
        "--source", type=Path, default=GOLDEN_FILE, help="golden .json or inbox .jsonl"
    )
    parser.add_argument("--split", choices=["tuned", "heldout", "all"], default="tuned")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args(argv)

    try:
        check_url(args.url)
        records = load_source(args.source, args.split)
    except InboxError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    shown = args.source.name if args.source.is_absolute() else args.source.relative_to(REPO_ROOT)
    print(f"{len(records)} record(s) read from {shown}")
    result = import_inbox(
        records, lambda rec: post_record(args.url, rec), dry_run=args.dry_run, limit=args.limit
    )
    if args.dry_run:
        print(f"Dry run: would import {result.would_import} record(s) to {args.url}. Nothing sent.")
        return 0
    print(
        f"created {result.created}, already imported {result.duplicates}, "
        f"failed {len(result.failed)}"
    )
    if result.failed:
        print("failed ids: " + ", ".join(result.failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
