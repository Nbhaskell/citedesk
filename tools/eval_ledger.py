"""The ledgers of the locked sets: the held-out split (D-061, D-062) and the sealed set (D-071).

Each is looked at once, by one fixed system. The rules are the same; only the file and the words
differ. `eval/heldout_ledger.json` and `eval/sealed_ledger.json` are committed. Starting a run
writes to the ledger *before* the first item is read, so a run that crashes still leaves its trace.
The rules, in code and tested (written for the held-out set; the sealed set says "sealed"):

- The first held-out run of a system declares how many passes it will make (1 to 5). Later passes of
  the same system, up to that number, need no reason: they exist to measure run-to-run spread.
- Another pass beyond that number, a fresh start of a run that never finished, or a run of a
  *different* system (the held-out set has been used once; it is spent for the next change) is
  refused unless a written reason is given. The reason is kept in the ledger.
- A run that did not finish can be resumed by its id. That uses no pass.

A "system" is the identity in `eval_run.system_identity`: the committed code tree and the universe
tree (not the commit id, so committing the ledger itself does not make a new system), the model, the
prompt versions, the settings, the knowledge base's configuration and the split that is run.
The ledger holds ids, counts and dates. Never message text.
"""

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FORMATS = {"heldout": "heldout-ledger-v1", "sealed": "sealed-ledger-v1"}
NAMES = {"heldout": "held-out", "sealed": "sealed"}
FORMAT = FORMATS["heldout"]
MIN_PASSES, MAX_PASSES = 1, 5
MIN_REASON_CHARS = 20


class LedgerRefused(Exception):
    """The held-out ledger does not allow this run. The message says why and what would."""


def empty(kind: str = "heldout") -> dict[str, Any]:
    decisions = "D-061 and D-062" if kind == "heldout" else "D-071"
    return {
        "format": FORMATS[kind],
        "note": (
            f"Every {NAMES[kind]} run of the evaluation, written when the run starts. The "
            f"{NAMES[kind]} set is run once, by one fixed system; see docs/DECISIONS.md "
            f"{decisions}."
        ),
        "evaluations": [],
    }


def load(path: Path, kind: str = "heldout") -> dict[str, Any]:
    if not path.exists():
        return empty(kind)
    data: dict[str, Any] = json.loads(path.read_text("utf-8"))
    if data.get("format") != FORMATS[kind]:
        raise LedgerRefused(f"{path.name} is not a {NAMES[kind]} ledger (format {FORMATS[kind]!r})")
    return data


def _name(ledger: dict[str, Any]) -> str:
    """The word for this ledger's set in a message."""
    for kind, fmt in FORMATS.items():
        if ledger.get("format") == fmt:
            return NAMES[kind]
    return "held-out"


def save(path: Path, ledger: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    os.replace(temporary, path)


def system_id(identity: dict[str, Any]) -> str:
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class Authorization:
    evaluation_index: int | None  # None: a new evaluation
    pass_number: int
    passes_declared: int
    outside_plan: bool
    justification: str | None
    resume: bool


def _reason_ok(justify: str | None) -> bool:
    return justify is not None and len(justify.strip()) >= MIN_REASON_CHARS


def _need_reason(why: str, justify: str | None) -> str:
    """The reason to record, or a refusal that says what was refused and how to get past it."""
    if justify is None or not _reason_ok(justify):
        raise LedgerRefused(
            f"{why}. To go ahead anyway, give a reason of at least {MIN_REASON_CHARS} characters "
            "with --justify; it is written into the ledger."
        )
    return justify.strip()


def _check_passes(passes: int) -> None:
    if not MIN_PASSES <= passes <= MAX_PASSES:
        raise LedgerRefused(f"passes must be between {MIN_PASSES} and {MAX_PASSES}, not {passes}")


def authorize(
    ledger: dict[str, Any],
    identity: dict[str, Any],
    *,
    passes: int | None = None,
    justify: str | None = None,
    resume_run_id: str | None = None,
) -> Authorization:
    """Decide whether this system may make a held-out run now. Raises `LedgerRefused` if not."""
    wanted = system_id(identity)
    name = _name(ledger)
    evaluations: list[dict[str, Any]] = ledger["evaluations"]

    if resume_run_id is not None:
        for index, evaluation in enumerate(evaluations):
            for run in evaluation["runs"]:
                if run["run_id"] == resume_run_id and run["status"] == "started":
                    if evaluation["system_id"] != wanted:
                        raise LedgerRefused(
                            "this is a different system from the one that started that run; "
                            "check out the same commit and use the same settings to resume it"
                        )
                    return Authorization(
                        index, run["pass"], evaluation["passes_declared"], False, None, True
                    )
        raise LedgerRefused(f"run {resume_run_id!r} is not an unfinished {name} run")

    if passes is not None:
        _check_passes(passes)
    match = next(
        ((i, e) for i, e in enumerate(evaluations) if e["system_id"] == wanted),
        None,
    )

    if match is None:
        reason = None
        if evaluations:
            reason = _need_reason(
                f"the {name} set has already been run on a different system, so it is spent "
                "for this one",
                justify,
            )
        if passes is None:
            raise LedgerRefused(
                f"the first {name} run of a system must declare how many passes it will make: "
                f"use --{'heldout' if name == 'held-out' else 'sealed'}-passes N (1 to 5)"
            )
        return Authorization(None, 1, passes, reason is not None, reason, False)

    index, evaluation = match
    declared = evaluation["passes_declared"]
    if passes is not None and passes != declared:
        raise LedgerRefused(
            f"this system's {name} evaluation declared {declared} passes; "
            f"it cannot be changed to {passes}"
        )
    runs = evaluation["runs"]
    reason = None
    if any(r["status"] == "started" for r in runs):
        reason = _need_reason(
            f"an earlier {name} run of this system never finished. Resume it with "
            "--resume RUN_ID (that uses no pass); starting again would be a second look",
            justify,
        )
    elif len(runs) >= declared:
        reason = _need_reason(
            f"all the passes declared for this system are used ({len(runs)} of {declared})",
            justify,
        )
    return Authorization(index, len(runs) + 1, declared, reason is not None, reason, False)


def record_start(
    ledger: dict[str, Any],
    auth: Authorization,
    identity: dict[str, Any],
    *,
    run_id: str,
    run_file: str,
    now: str,
) -> None:
    """Write the run into the ledger. Call this before the first held-out item is read."""
    if auth.resume:
        if auth.evaluation_index is None:
            raise LedgerRefused("a resumed run belongs to an evaluation already in the ledger")
        for run in ledger["evaluations"][auth.evaluation_index]["runs"]:
            if run["run_id"] == run_id:
                run.setdefault("resumed_at", []).append(now)
        return
    run = {
        "run_id": run_id,
        "run_file": run_file,
        "pass": auth.pass_number,
        "status": "started",
        "started_at": now,
        "finished_at": None,
        "items": None,
        "failed": None,
        "outside_plan": auth.outside_plan,
        "justification": auth.justification,
    }
    if auth.evaluation_index is None:
        ledger["evaluations"].append(
            {
                "system_id": system_id(identity),
                "identity": identity,
                "passes_declared": auth.passes_declared,
                "created_at": now,
                "runs": [run],
            }
        )
    else:
        ledger["evaluations"][auth.evaluation_index]["runs"].append(run)


def record_finish(
    ledger: dict[str, Any], run_id: str, *, now: str, items: int, failed: int
) -> None:
    for evaluation in ledger["evaluations"]:
        for run in evaluation["runs"]:
            if run["run_id"] == run_id:
                run.update(status="completed", finished_at=now, items=items, failed=failed)
                return
    raise KeyError(run_id)


def heldout_problems(
    *,
    allow_heldout: bool,
    limit: int | None,
    dirty: bool,
    git_known: bool,
    split: str = "heldout",
) -> list[str]:
    """Reasons a held-out request is refused before the ledger or any item is touched."""
    if split != "heldout":
        return []
    problems: list[str] = []
    if not allow_heldout:
        problems.append(
            "the held-out split is run once, by the evaluation, and never used to tune: "
            "ask for it explicitly with --allow-heldout"
        )
    if limit is not None:
        problems.append("a held-out run is the whole split: --limit is not allowed with it")
    if not git_known:
        problems.append("git did not answer, so the system cannot be pinned to a commit")
    elif dirty:
        problems.append(
            "there are uncommitted changes to the system: commit them first, so the run names a "
            "fixed system (changes under eval/ are ignored)"
        )
    return problems


def sealed_problems(
    *,
    split: str,
    confirmed: bool,
    limit: int | None,
    dirty: bool,
    git_known: bool,
    hash_matches: bool,
    hash_name: str | None = None,
) -> list[str]:
    """Reasons a sealed-set request is refused before the ledger or any item is touched (D-071)."""
    if split != "sealed":
        return []
    problems: list[str] = []
    if not confirmed:
        problems.append(
            "the sealed set is run once, by the evaluation, and never used to choose or tune: "
            "ask for it explicitly with --confirm-sealed-once"
        )
    if limit is not None:
        problems.append("a sealed run is the whole set: --limit is not allowed with it")
    if not git_known:
        problems.append("git did not answer, so the system cannot be pinned to a commit")
    elif dirty:
        problems.append(
            "there are uncommitted changes to the system: commit them first, so the run names a "
            "fixed system (changes under eval/ are ignored)"
        )
    if not hash_matches:
        problems.append(
            "the sealed file is missing or does not match the committed hash "
            f"({hash_name or 'citedesk_sealed.sha256'}): it may have been changed since it was "
            "sealed"
        )
    return problems
