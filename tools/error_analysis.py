"""Error analysis of saved evaluation runs: a confusion matrix of the primary intent and a list of
the misses, with whether each also gave the wrong route. Reads saved runs and the labels; calls no
model. Prints ids, labels and counts only, never message text.

    python -m tools.error_analysis --split heldout --md eval/reports/heldout-error-analysis.md

The heldout split is spent (D-064): analysing it is allowed, changing the system because of it is
what spends it, and the next claim needs the sealed set (D-071).
"""

import argparse
import glob
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

NOT_READ = "(not read)"


def analyse(gold_items: list[dict[str, Any]], passes: list[list[dict[str, Any]]]) -> dict[str, Any]:
    """`passes` is one list of run items per pass of the same system."""
    gold = {item["id"]: item for item in gold_items}
    by_item: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in passes:
        for got in run:
            by_item[got["id"]].append(got)

    confusion: Counter[tuple[str, str]] = Counter()
    misses: list[dict[str, Any]] = []
    for item_id, gots in by_item.items():
        labels = gold[item_id]["labels"]
        expected = labels["primary_intent"]
        predicted = [g["primary_intent"] or NOT_READ for g in gots]
        for p in predicted:
            if p != expected:
                confusion[(expected, p)] += 1
        if any(p != expected for p in predicted):
            routes = [g["route"] for g in gots]
            misses.append(
                {
                    "id": item_id,
                    "category": gold[item_id]["category"],
                    "expected": expected,
                    "predicted": predicted,
                    "expected_reasons": labels["expected_reason_codes"],
                    "expected_route": labels["expected_route"],
                    "routes": routes,
                    "route_wrong": any(r != labels["expected_route"] for r in routes),
                }
            )
    misses.sort(key=lambda m: (m["category"], m["id"]))
    return {"confusion": confusion, "misses": misses, "items": len(by_item)}


def render(result: dict[str, Any], passes: int) -> str:
    misses = result["misses"]
    changed_route = [m for m in misses if m["route_wrong"]]
    lines = [
        "# Held-out error analysis (primary intent)",
        "",
        "> SYNTHETIC DATA. Ids, labels and counts only; no message text.",
        "",
        f"{result['items']} items, {passes} passes of one system. {len(misses)} items had a wrong "
        f"primary intent in at least one pass; {len(changed_route)} of them also had a wrong "
        "route.",
        "",
        "## Confusion (expected, predicted; wrong pairs only, summed over passes)",
        "",
        "| Expected | Predicted | Count |",
        "|---|---|---|",
    ]
    for (expected, predicted), n in sorted(
        result["confusion"].items(), key=lambda x: (-x[1], x[0])
    ):
        lines.append(f"| {expected} | {predicted} | {n} |")
    lines += [
        "",
        "## Items with a wrong primary intent",
        "",
        "| Category | Item | Expected | Predicted | Expected route | Route wrong |",
        "|---|---|---|---|---|---|",
    ]
    for m in misses:
        predicted = ", ".join(sorted(set(m["predicted"])))
        wrong = "yes" if m["route_wrong"] else "no"
        lines.append(
            f"| {m['category']} | `{m['id']}` | {m['expected']} | {predicted} | "
            f"{m['expected_route']} | {wrong} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument("--split", default="heldout", choices=("tuned", "heldout"))
    parser.add_argument("--golden", default="eval/golden/citedesk_v1.json")
    parser.add_argument("--md", help="write the report here")
    args = parser.parse_args(argv)

    golden = json.loads(Path(args.golden).read_text("utf-8"))["items"]
    gold_items = [i for i in golden if i["split"] == args.split]
    paths = sorted(glob.glob(f"eval/runs/eval-{args.split}-{args.split}-*-p?.run.json"))
    if not paths:
        print(f"No saved {args.split} runs found in eval/runs/.")
        return 1
    passes = [json.loads(Path(p).read_text("utf-8"))["items"] for p in paths]
    text = render(analyse(gold_items, passes), passes=len(passes))
    if args.md:
        Path(args.md).write_text(text, encoding="utf-8")
        print(f"Wrote {args.md}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
