"""A cost-weighted route score, next to two simple policies (D-094).

Why. Route accuracy counts every wrong route the same: a gas leak that gets a draft reply and a
plain question escalated to a person are one miss each. They are not equally bad. This scorer gives
each kind of route error a cost, and costs two policies that need no model on the same items:
escalate everything (a person writes every reply) and draft everything (no escalation at all).

The costs are ASSUMPTIONS, in rough minutes of a person's time, fixed before any run was scored:

- `missed_safety` 100: a health or safety message that is not escalated.
- `lost_message` 50: a real message archived, so nobody sees it.
- `missed_escalation` 20: a message that needs a person gets a draft or a request for details; a
  reviewer may approve it (the reviewer trial caught 0 of 5 planted problems).
- `extra_escalation` 4: a message the desk could answer goes to a person, who writes a reply by
  hand (about 5 minutes against about 1 to check a draft). A failed item counts here too.
- `spam_kept` 1: spam that a person has to look at and archive.
- `wrong_kind_of_reply` 1: a draft where details should be asked for, or the other way round.

The counts per kind are reported as well, so other costs can be applied by hand.

    python -m tools.route_cost [--split tuned|heldout] [--md PATH] RUN.run.json [RUN ...]

The sealed split is refused: its labels stay unopened (D-071). Reports hold ids, routes and
counts only: no message text.
"""

import argparse
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.golden import GOLDEN_FILE

HEALTH_SAFETY = "HEALTH_SAFETY"
KINDS = (
    "right",
    "missed_safety",
    "lost_message",
    "missed_escalation",
    "extra_escalation",
    "spam_kept",
    "wrong_kind_of_reply",
)
COSTS: Mapping[str, int] = {
    "missed_safety": 100,
    "lost_message": 50,
    "missed_escalation": 20,
    "extra_escalation": 4,
    "spam_kept": 1,
    "wrong_kind_of_reply": 1,
}
POLICIES = (("Escalate everything", "escalate"), ("Draft everything", "draft_reply"))


def outcome(labels: Mapping[str, Any], got: str | None) -> str:
    """The kind of result for one item. A failed item (no route) waits for a person, like an
    escalation."""
    wanted = labels["expected_route"]
    got = got or "escalate"
    if got == wanted:
        return "right"
    if HEALTH_SAFETY in labels.get("expected_reason_codes", []) and got != "escalate":
        return "missed_safety"
    if got == "archive":
        return "lost_message"
    if wanted == "escalate":
        return "missed_escalation"
    if wanted == "archive":
        return "spam_kept"
    if got == "escalate":
        return "extra_escalation"
    return "wrong_kind_of_reply"


def cost(gold: Mapping[str, Mapping[str, Any]], routes: Mapping[str, str | None]) -> dict[str, Any]:
    missing = sorted(set(gold) - set(routes))
    if missing:
        raise ValueError(f"items not in the run: {missing[:5]}")
    kinds = {item_id: outcome(labels, routes[item_id]) for item_id, labels in gold.items()}
    counts = Counter(kinds.values())
    total = sum(COSTS.get(kind, 0) * n for kind, n in counts.items())
    return {
        "n": len(gold),
        "counts": {kind: counts.get(kind, 0) for kind in KINDS},
        "total": total,
        "per_100": 100 * total / len(gold) if gold else 0.0,
        "errors": {
            kind: sorted(i for i, k in kinds.items() if k == kind)
            for kind in KINDS
            if kind != "right" and COSTS[kind] >= COSTS["missed_escalation"]
        },
    }


def break_even(result: Mapping[str, Any], escalate_all: Mapping[str, Any]) -> float | None:
    """The cost of one missed escalation at which the run costs the same as escalating everything,
    with the other costs unchanged. None when the run missed no escalation. Above this value,
    escalating everything is cheaper."""
    missed = result["counts"]["missed_escalation"]
    if missed == 0:
        return None
    rest = result["total"] - missed * COSTS["missed_escalation"]
    return (escalate_all["total"] - rest) / missed


def policy(gold: Mapping[str, Any], route: str) -> dict[str, str | None]:
    return {item_id: route for item_id in gold}


def labels_for(items: Sequence[dict[str, Any]], split: str) -> dict[str, dict[str, Any]]:
    if split == "sealed" or any(i.get("split") == "sealed" for i in items):
        raise ValueError("the sealed split is never used here")
    return {i["id"]: i["labels"] for i in items if i.get("split") == split}


def routes_of(run: Mapping[str, Any]) -> dict[str, str | None]:
    return {r["id"]: r.get("route") for r in run["items"]}


def _row(name: str, result: Mapping[str, Any]) -> str:
    c = result["counts"]
    return (
        f"| {name} | {result['per_100']:.0f} | {c['missed_safety']} | {c['lost_message']} | "
        f"{c['missed_escalation']} | {c['extra_escalation']} | {c['spam_kept']} | "
        f"{c['wrong_kind_of_reply']} | {c['right']} of {result['n']} |"
    )


def render(split: str, runs: Sequence[tuple[str, dict[str, Any]]], gold: Mapping) -> str:
    lines = [
        "# Cost-weighted route score",
        "",
        "> SYNTHETIC DATA. Ids, routes and counts only; no message text.",
        "",
        f"Split: **{split}** ({len(gold)} items). Costs are ASSUMPTIONS in rough minutes of a "
        "person's time, fixed before scoring (D-094): missed safety 100, real message archived "
        "50, missed escalation 20, extra escalation 4, spam kept 1, wrong kind of reply 1. "
        "Lower is better.",
        "",
        "| System | Cost per 100 | Missed safety | Lost | Missed escalation | Extra escalation "
        "| Spam kept | Wrong reply kind | Right |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    lines += [_row(name, result) for name, result in runs]
    for label, route in POLICIES:
        lines.append(_row(f"{label} (no model)", cost(gold, policy(gold, route))))
    everything = cost(gold, policy(gold, "escalate"))
    lines += ["", "## Break-even with escalating everything", ""]
    for name, result in runs:
        value = break_even(result, everything)
        lines.append(
            f"- `{name}`: no missed escalation, so it is cheaper whenever its other errors are"
            if value is None
            else f"- `{name}`: the two cost the same when one missed escalation costs {value:.1f} "
            "(the assumed cost is 20); above that, escalating everything is cheaper"
        )
    for name, result in runs:
        listed = {k: v for k, v in result["errors"].items() if v}
        if listed:
            lines += ["", f"## Costly errors in `{name}`", ""]
            lines += [f"- {kind}: {', '.join(ids)}" for kind, ids in listed.items()]
    lines += [
        "",
        "## What this cannot tell you",
        "",
        "- The costs are assumptions. The counts per kind are given so other costs can be applied.",
        "- The mix of the evaluation sets is not a real inbox: they hold more messages that should "
        "escalate than a business would see, which favours escalating everything.",
        "- An escalated message is assumed to be handled well by a person, and a draft that should "
        "not exist is costed once, not by what happens if it is approved.",
        "",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("runs", type=Path, nargs="+")
    parser.add_argument("--split", choices=("tuned", "heldout"), default="tuned")
    parser.add_argument("--golden", type=Path, default=GOLDEN_FILE)
    parser.add_argument("--md", type=Path)
    args = parser.parse_args(argv)

    gold = labels_for(json.loads(args.golden.read_text(encoding="utf-8"))["items"], args.split)
    runs = []
    for path in args.runs:
        run = json.loads(path.read_text(encoding="utf-8"))
        name = path.name.removesuffix(".run.json").removesuffix(".drafts.json")
        runs.append((name, cost(gold, routes_of(run))))
    text = render(args.split, runs, gold)
    if args.md:
        args.md.parent.mkdir(parents=True, exist_ok=True)
        args.md.write_text(text, encoding="utf-8", newline="\n")
        print(f"Wrote {args.md}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
