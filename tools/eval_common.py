"""Shared pieces of the Phase 7 evaluation tools: splits and their hashes, provenance, file I/O.

Nothing here calls the system under test. The split hash covers the *selected split's items* (their
messages and labels), not the whole golden file, so the tuned split's hash does not move when
held-out items are added to the file.
"""

import hashlib
import json
import os
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from citedesk.providers.ollama import LOOPBACK_HOSTS
from tools.golden import GOLDEN_FILE, REPO_ROOT, SEALED_FILE, SEALED_HASH_FILE, SETS

RUNS_DIR = REPO_ROOT / "eval/runs"
REPORTS_DIR = REPO_ROOT / "eval/reports"
LEDGER_FILE = REPO_ROOT / "eval/heldout_ledger.json"
SEALED_LEDGER_FILE = REPO_ROOT / "eval/sealed_ledger.json"
# The invented electrician's set (D-099, D-100) is a locked held-out set with its own ledger.
FERNHOLLOW_LEDGER_FILE = REPO_ROOT / "eval/fernhollow_ledger.json"
# Each sealed set has its own ledger (D-071, D-104).
SEALED_LEDGERS = {
    "kestrel": SEALED_LEDGER_FILE,
    "kestrel-2": REPO_ROOT / "eval/sealed_v2_ledger.json",
    "fernhollow-2": REPO_ROOT / "eval/fernhollow_sealed_ledger.json",
    "kestrel-3": REPO_ROOT / "eval/sealed_v3_ledger.json",
    "fernhollow-3": REPO_ROOT / "eval/fernhollow_sealed_v2_ledger.json",
}
GOLDEN_SETS = tuple(SETS)
SPLITS = ("tuned", "heldout", "sealed")
LOCKED_SPLITS = ("heldout", "sealed")

# What changes while an evaluation is running without changing the system under test.
IGNORED_FOR_DIRTY = (
    "eval/heldout_ledger.json",
    "eval/sealed_ledger.json",
    "eval/fernhollow_ledger.json",
    "eval/sealed_v2_ledger.json",
    "eval/fernhollow_sealed_ledger.json",
    "eval/sealed_v3_ledger.json",
    "eval/fernhollow_sealed_v2_ledger.json",
    "eval/runs/",
    "eval/reports/",
)

# The parts of rag-project's status that describe its configuration, not its clock.
RAG_IDENTITY_KEYS = ("chat_model", "embed_model", "thinking", "split_search", "files", "chunks")


def canonical_sha256(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def select_split(golden: dict[str, Any], split: str) -> list[dict[str, Any]]:
    if split not in SPLITS:
        raise ValueError(f"unknown split {split!r}; the splits are {', '.join(SPLITS)}")
    return [item for item in golden["items"] if item["split"] == split]


def golden_file_for(split: str, golden_set: str = "kestrel") -> Path:
    """The file the labels of a split are in: the sealed set is kept apart (D-071), and a named
    set other than the plumber's has its own file and held-out items only (D-100)."""
    if golden_set != "kestrel":
        target = SETS[golden_set]
        if split not in target.splits:
            raise ValueError(
                f"the {golden_set} set holds only {', '.join(target.splits)} items, not {split!r}"
            )
        return target.golden_file
    return SEALED_FILE if split == "sealed" else GOLDEN_FILE


def sealed_ledger_file_for(golden_set: str) -> Path | None:
    """The ledger of a set's sealed run, or None if the set has no sealed split."""
    return SEALED_LEDGERS.get(golden_set)


def sealed_files_for(golden_set: str) -> tuple[Path, Path] | None:
    """The sealed file and its committed hash file, or None if the set has none."""
    if golden_set == "kestrel":
        return SEALED_FILE, SEALED_HASH_FILE
    target = SETS.get(golden_set)
    if target is None or target.hash_file is None:
        return None
    return target.golden_file, target.hash_file


def ledger_file_for(golden_set: str) -> Path:
    """The ledger of a set's held-out runs."""
    return FERNHOLLOW_LEDGER_FILE if golden_set == "fernhollow" else LEDGER_FILE


def split_sha256(items: Iterable[dict[str, Any]]) -> str:
    """Hash of the items of one split, in file order. Unaffected by items of other splits."""
    return canonical_sha256(list(items))


def file_sha256(path: Path = GOLDEN_FILE) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_atomic(path: Path, data: Any) -> None:
    """Write a JSON file so a reader (or a crash) sees the old file or the new one, never half."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    os.replace(temporary, path)


# --- git ---------------------------------------------------------------------------------------


def dirty_paths(porcelain: str, ignore: Iterable[str] = IGNORED_FOR_DIRTY) -> list[str]:
    """Paths `git status --porcelain` lists that are not under an ignored path."""
    ignored = tuple(ignore)
    paths: list[str] = []
    for line in porcelain.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].split(" -> ")[-1].strip().strip('"').replace("\\", "/")
        if not path.startswith(ignored):
            paths.append(path)
    return paths


def _git(*args: str) -> str | None:
    try:
        done = subprocess.run(  # noqa: S603 (fixed arguments)
            ["git", *args],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return done.stdout.strip()


def git_state() -> dict[str, Any]:
    """Commit, whether the tree has uncommitted changes, and the tree ids of the system's code.

    `code_tree` and `universe_tree` are git's ids for the committed `citedesk/` and `universe/`
    folders: they change when the system changes and not when only the ledger is committed.
    """
    status = _git("status", "--porcelain")
    return {
        "commit": _git("rev-parse", "HEAD"),
        "dirty": None if status is None else bool(dirty_paths(status)),
        "dirty_paths": None if status is None else len(dirty_paths(status)),
        "code_tree": _git("rev-parse", "HEAD:citedesk"),
        "universe_tree": _git("rev-parse", "HEAD:universe"),
    }


# --- the knowledge base's configuration --------------------------------------------------------

GetFn = Callable[[str, float], dict[str, Any]]


def http_get_json(url: str, timeout_s: float) -> dict[str, Any]:
    request = urllib.request.Request(url, method="GET")  # noqa: S310 (checked by the caller)
    with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
        body = json.loads(response.read())
    if not isinstance(body, dict):
        raise ValueError("not an object")
    return body


def rag_status(url: str, get: GetFn | None = None) -> dict[str, Any]:
    """rag-project's `/api/status`, to record what the knowledge base was when the run started.

    Only a loopback address is contacted. A failure is recorded as a code, so a run header never
    fails because the status could not be read; the runner's own questions will fail loudly.
    """
    parsed = urlparse(url)
    if parsed.hostname not in LOOPBACK_HOSTS:
        return {"error": "not_local"}
    try:
        body = (get or http_get_json)(f"{url.rstrip('/')}/api/status", 5.0)
    except (OSError, ValueError, urllib.error.URLError):
        return {"error": "unavailable"}
    keep = (*RAG_IDENTITY_KEYS, "documents", "last_sync", "last_change")
    return {key: body[key] for key in keep if key in body}


def rag_identity(status: dict[str, Any]) -> dict[str, Any]:
    return {key: status.get(key) for key in RAG_IDENTITY_KEYS} | (
        {"error": status["error"]} if "error" in status else {}
    )
