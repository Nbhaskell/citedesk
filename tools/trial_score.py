"""Score the reviewer trial (docs/REVIEW_TRIAL.md) after the sitting.

    python -m tools.trial_score --db data/trial.db --md eval/reports/review-trial.md \\
        --json eval/reports/review-trial.json [--exclude 17 21] [--unaided 140 95 180 120 150]

Reads the reviewer's decisions and the app's own `review_seconds` from the trial database and the
plan written by `tools.trial_prepare`. The output holds ids, kinds, decisions and numbers, never
message or draft text. There is no pass mark: the numbers are reported with the protocol's limits.
"""

import argparse
import json
import math
import re
import sqlite3
import statistics
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from citedesk import repo
from citedesk.db import connect
from tools import eval_common as common

SCORED = ("ordinary", "planted")
DECISIONS = ("approve", "edit_approve", "reject", "escalate")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def percentile(values: list[int], q: float) -> float:
    """Nearest-rank percentile (q in 0..1) of a non-empty list."""
    ordered = sorted(values)
    return float(ordered[max(0, math.ceil(q * len(ordered)) - 1)])


def timing(values: list[int]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "median": None, "p90": None, "min": None, "max": None}
    return {
        "n": len(values),
        "median": float(statistics.median(values)),
        "p90": percentile(values, 0.9),
        "min": min(values),
        "max": max(values),
    }


def _binomial_tail(n: int, k: int, p: float, *, at_least: bool) -> float:
    if at_least:
        return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k, n + 1))
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(0, k + 1))


def exact_interval(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """The Clopper-Pearson interval for k successes in n tries, found by bisection."""
    if n == 0:
        return (0.0, 1.0)

    def solve(target: Callable[[float], float], increasing: bool) -> float:
        low, high = 0.0, 1.0
        for _ in range(60):
            mid = (low + high) / 2
            if (target(mid) < alpha / 2) == increasing:
                low = mid
            else:
                high = mid
        return (low + high) / 2

    lower = (
        0.0 if k == 0 else solve(lambda p: _binomial_tail(n, k, p, at_least=True), increasing=True)
    )
    upper = (
        1.0
        if k == n
        else solve(lambda p: _binomial_tail(n, k, p, at_least=False), increasing=False)
    )
    return (lower, upper)


def _first_decision(conn: sqlite3.Connection, inquiry_id: int) -> Any:
    reviews = [r for r in repo.list_reviews(conn, inquiry_id) if r.decision.value in DECISIONS]
    return reviews[0] if reviews else None


def entries(
    conn: sqlite3.Connection, plan: dict[str, Any], exclude: set[int]
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in plan["order"]:
        review = _first_decision(conn, row["inquiry_id"])
        decision = review.decision.value if review else None
        caught: bool | None = None
        if row["role"] == "planted" and review is not None:
            if decision == "approve":
                caught = False
            elif decision == "edit_approve":
                caught = _norm(row["marker"]) not in _norm(review.edited_body or "")
            else:
                caught = True
        out.append(
            {
                "position": row["position"],
                "inquiry_id": row["inquiry_id"],
                "item_id": row["item_id"],
                "role": row["role"],
                "kind": row["kind"],
                "decision": decision,
                "seconds": review.review_seconds if review else None,
                "timed": review is not None
                and review.review_seconds is not None
                and row["inquiry_id"] not in exclude
                and row["role"] in SCORED,
                "caught": caught,
            }
        )
    return out


def score(
    conn: sqlite3.Connection,
    plan: dict[str, Any],
    *,
    exclude: frozenset[int] | set[int] = frozenset(),
    unaided: list[int] | None = None,
) -> dict[str, Any]:
    rows = entries(conn, plan, set(exclude))
    by_role: dict[str, dict[str, Any]] = {}
    for role in SCORED:
        mine = [r for r in rows if r["role"] == role]
        decided = [r["decision"] for r in mine]
        by_role[role] = {
            "n": len(mine),
            "not_reviewed": sum(d is None for d in decided),
            "decisions": {name: decided.count(name) for name in DECISIONS},
            "time": timing([r["seconds"] for r in mine if r["timed"]]),
        }
    planted = [r for r in rows if r["role"] == "planted"]
    reviewed = [r for r in planted if r["caught"] is not None]
    caught = sum(bool(r["caught"]) for r in reviewed)
    low, high = exact_interval(caught, len(reviewed))
    return {
        "format": "review-trial-scores-v1",
        "seed": plan["seed"],
        "model": plan.get("model"),
        "excluded_from_timing": sorted(exclude),
        "by_role": by_role,
        "all_scored_time": timing([r["seconds"] for r in rows if r["timed"]]),
        "planted_caught": {
            "caught": caught,
            "reviewed": len(reviewed),
            "of": len(planted),
            "interval_95": [round(low, 3), round(high, 3)],
        },
        "unaided_seconds": timing(unaided or []) if unaided else None,
        "rows": rows,
    }


def _secs(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0f} s"


def markdown(scores: dict[str, Any]) -> str:
    caught = scores["planted_caught"]
    lines = [
        "# Reviewer trial",
        "",
        "> SYNTHETIC DATA. Every customer and message here is invented. One reviewer, who also "
        "built the system.",
        "",
        "Protocol: `docs/REVIEW_TRIAL.md`, written before the trial. No pass mark.",
        "",
        "## Review time (the app's own `review_seconds`)",
        "",
        "| Drafts | n | Median | p90 | Range |",
        "|---|---|---|---|---|",
    ]
    for label, block in (
        ("All scored", scores["all_scored_time"]),
        ("Ordinary", scores["by_role"]["ordinary"]["time"]),
        ("With a planted problem", scores["by_role"]["planted"]["time"]),
    ):
        span = "n/a" if block["n"] == 0 else f"{block['min']} to {block['max']} s"
        lines.append(
            f"| {label} | {block['n']} | {_secs(block['median'])} | "
            f"{_secs(block['p90'])} | {span} |"
        )
    if scores["excluded_from_timing"]:
        lines += [
            "",
            f"Left out of the timing (interrupted or paused): inquiries "
            f"{', '.join(map(str, scores['excluded_from_timing']))}.",
        ]
    if scores["unaided_seconds"]:
        u = scores["unaided_seconds"]
        lines += [
            "",
            f"Writing a reply from the documents without a draft (optional, {u['n']} replies, "
            f"stopwatch): median {_secs(u['median'])}, range {u['min']} to {u['max']} s.",
        ]
    lines += [
        "",
        "## Decisions",
        "",
        "| Drafts | n | Approved | Edited and approved | Rejected | Escalated | Not reviewed |",
        "|---|---|---|---|---|---|---|",
    ]
    for role, label in (("ordinary", "Ordinary"), ("planted", "With a planted problem")):
        b = scores["by_role"][role]
        d = b["decisions"]
        lines.append(
            f"| {label} | {b['n']} | {d['approve']} | {d['edit_approve']} | {d['reject']} | "
            f"{d['escalate']} | {b['not_reviewed']} |"
        )
    lines += [
        "",
        "## Planted problems",
        "",
        f"The reviewer caught the planted problem on **{caught['caught']} of "
        f"{caught['reviewed']}** reviewed drafts with one ({caught['of']} planted). "
        f"A count this small gives a wide exact 95% interval: {caught['interval_95'][0]:.2f} to "
        f"{caught['interval_95'][1]:.2f} as a share. A draft counts as caught if it was rejected, "
        "escalated, or edited so the planted text is gone.",
        "",
        "| Position | Item | Kind | Decision | Seconds | Caught |",
        "|---|---|---|---|---|---|",
    ]
    for r in scores["rows"]:
        if r["role"] != "planted":
            continue
        lines.append(
            f"| {r['position']} | `{r['item_id']}` | {r['kind']} | {r['decision'] or 'none'} | "
            f"{r['seconds'] if r['seconds'] is not None else 'n/a'} | "
            f"{'n/a' if r['caught'] is None else 'yes' if r['caught'] else 'no'} |"
        )
    lines += [
        "",
        "## What this cannot tell you",
        "",
        "- One reviewer who also built the system: they know the screens and what the checks do, "
        "so times and the catch count flatter the system.",
        "- The reviewer already knew some kinds of planted problem from earlier discussion of the "
        "weaknesses, so was not naive to them.",
        "- A high share of bad drafts (6 of 20) makes people more careful than they would be when "
        "problems are rare: the catch count is probably an upper bound.",
        "- Six planted drafts cannot give a rate; read the counts.",
        "- Invented messages and an invented business: this shows how the screens work for one "
        "person, not how a real front desk would cope.",
        "- It does not measure whether the model reads messages correctly (the intent accuracy in "
        "`eval/reports/`).",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--db", type=Path, default=Path("data/trial.db"))
    parser.add_argument("--plan", type=Path, default=Path("eval/trial/plants.json"))
    parser.add_argument("--md", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument(
        "--exclude", type=int, nargs="*", default=[], help="inquiry ids interrupted mid-review"
    )
    parser.add_argument("--unaided", type=int, nargs="*", help="seconds taken to write replies")
    args = parser.parse_args(argv)
    plan = json.loads(args.plan.read_text("utf-8"))
    conn = connect(args.db)
    try:
        scores = score(conn, plan, exclude=set(args.exclude), unaided=args.unaided)
    finally:
        conn.close()
    text = markdown(scores)
    if args.md:
        args.md.parent.mkdir(parents=True, exist_ok=True)
        args.md.write_text(text, encoding="utf-8", newline="\n")
    if args.json:
        common.write_json_atomic(args.json, scores)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
