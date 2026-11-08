"""A blind intent-labelling sheet and an agreement scorer (D-088).

Why. Primary-intent accuracy is 73.1% on the sealed set against a target of 85% (D-087), and the
labels were written by one labeller who also wrote the system. A second labeller, working from the
same labelling rules and not shown the existing labels, shows how much of the gap is doubt about
the labels and how much is model error.

Commands (run from the repo root; nothing here calls a model):

    python -m tools.label_agreement sheet [--n 60] [--seed 0]
    python -m tools.label_agreement score [--run eval/runs/<id>.run.json] [--md PATH]

`sheet` picks items from the tuned and held-out splits (never the sealed set), writes a sheet with
the message only, an order file mapping sheet numbers to item ids, and an empty labels file keyed by
sheet number. The sheet and order file go to `eval/runs/` (git-ignored); the labels file goes to
`eval/labels/`. `score` reads the labels file and writes ids, labels and counts only: no message
text.
"""

import argparse
import hashlib
import json
import random
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from tools.golden import GOLDEN_FILE, REPO_ROOT, schema_enum
from tools.judge_drafts import cohens_kappa

INTENTS: tuple[str, ...] = schema_enum("intent")
SPLITS = ("tuned", "heldout")
RUNS_DIR = REPO_ROOT / "eval" / "runs"
LABELS_FILE = REPO_ROOT / "eval" / "labels" / "intent_agreement.labels.json"
SHEET_NAME = "intent-labelling-sheet.md"
ORDER_NAME = "intent-labelling-sheet.order.json"

# The rules are the ones the existing labels were written under (eval/golden/README.md, "Labelling
# rules"). The short meanings of the intents the README does not spell out are neutral glosses.
RULES = (
    "- `primary_intent` is the one thing the customer most wants answered.",
    "- Opening hours, service area, and what the business does: `service_question`. Terms "
    "(warranty, cancelling, payment, access, discounts): `policy_question`. Whether someone is "
    "free at a time: `availability_question`.",
    "- Asking for a visit: `booking_request`. Moving a visit: `booking_change`. Cancelling: "
    "`cancellation`.",
    "- Booking or availability is decided by what the customer asks. Asking whether someone is "
    'free, available or has an opening at a time ("is anyone free Friday?"): '
    "`availability_question`. Asking the business to come, book or look at a described problem, "
    'even as a question ("can you come Thursday?"): `booking_request`. A question about a visit '
    'that already exists ("is my visit still on for Friday?") is neither: `other`.',
    "- Gas smell, carbon monoxide, flooding, a burst pipe or sewage backing up: "
    "`health_or_safety`.",
    "- Marketing and bulk offers: `spam`. A real question inside an injection attempt keeps its "
    "real intent.",
)
GLOSS = {
    "pricing_question": "asks what something costs",
    "availability_question": "asks whether someone is free at a time",
    "booking_request": "asks for a visit",
    "booking_change": "asks to move a visit",
    "cancellation": "asks to cancel a visit",
    "policy_question": "asks about terms: warranty, cancelling, payment, access, discounts",
    "service_question": "asks about opening hours, service area, or what the business does",
    "complaint": "is unhappy about service already received",
    "health_or_safety": "reports a gas smell, carbon monoxide, flooding, a burst pipe or sewage",
    "billing_question": "asks about an invoice, receipt or charge already issued",
    "partnership_or_sales": "offers the business a product, service or arrangement",
    "spam": "is marketing, a bulk offer or a scam",
    "other": "anything else, including follow-ups and messages too unclear to classify",
}


# --- choosing the items ---


def select_items(items: Sequence[dict[str, Any]], n: int, seed: int = 0) -> list[dict[str, Any]]:
    """About `n` items, the mix of splits kept in proportion, in a shuffled order.

    Repeatable for a given seed. A sealed item is refused: the sealed set is spent and its labels
    must not be shown to anyone who might then change the system.
    """
    if any(i["split"] == "sealed" for i in items):
        raise ValueError("a sealed item cannot go on a labelling sheet")
    pool = [i for i in items if i["split"] in SPLITS]
    n = min(n, len(pool))
    rng = random.Random(seed)  # noqa: S311 (a sample, not a secret)
    by_split: dict[str, list[dict[str, Any]]] = {}
    for i in pool:
        by_split.setdefault(i["split"], []).append(i)
    quotas = {s: n * len(g) // len(pool) for s, g in by_split.items()}
    spare = sorted(by_split, key=lambda s: (-(n * len(by_split[s]) % len(pool)), s))
    for s in spare[: n - sum(quotas.values())]:
        quotas[s] += 1
    chosen: list[dict[str, Any]] = []
    for s in sorted(by_split):
        group = list(by_split[s])
        rng.shuffle(group)
        chosen.extend(group[: quotas[s]])
    rng.shuffle(chosen)
    return chosen


# --- the sheet and the labels file ---


def sheet_id(order: Sequence[str]) -> str:
    return hashlib.sha256("\n".join(order).encode("utf-8")).hexdigest()[:12]


def build_sheet(items: Sequence[dict[str, Any]]) -> tuple[str, list[str]]:
    """The sheet text and the item ids in sheet order. It shows the channel, subject and body only:
    never an id, a category, a note or a label."""
    lines = [
        "# Label these messages",
        "",
        "SYNTHETIC DATA. Every customer and message here is invented.",
        "",
        "For each message write its primary intent in the labels file, using one of the intents "
        "below. Decide only this: what does the customer most want answered? Add a number to "
        '`"unsure"` in the file when the call was close. Do not look at other files in this '
        "repository while labelling.",
        "",
        "## Rules",
        "",
        *RULES,
        "",
        "## Intents",
        "",
        *[f"- `{name}`: {GLOSS.get(name, 'see the rules above')}" for name in INTENTS],
        "",
        "Write the labels into the labels file as "
        '`{"labeller": "...", "labels": {"1": "spam", ...}, "unsure": ["4"]}`.',
        "",
    ]
    order: list[str] = []
    for number, it in enumerate(items, start=1):
        order.append(it["id"])
        lines += [
            f"## {number}.",
            "",
            f"Channel: {it['channel']}",
            f"Subject: {it['subject']}",
            "",
            *[f"> {line}" if line else ">" for line in str(it["body"]).splitlines()],
            "",
        ]
    return "\n".join(lines), order


def label_template(order: Sequence[str]) -> dict[str, Any]:
    return {
        "labeller": "",
        "sheet_id": sheet_id(order),
        "labels": {str(i + 1): "" for i in range(len(order))},
        "unsure": [],
    }


# --- scoring ---


def load_run_intents(path: Path) -> dict[str, str]:
    """Primary intent per item id from a saved run, for the items the model read."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        r["id"]: r["primary_intent"]
        for r in data["items"]
        if r.get("classified") and r.get("primary_intent")
    }


def score(
    golden: dict[str, dict[str, Any]],
    order: Sequence[str],
    labels_file: dict[str, Any],
    model: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Compare the second labeller's primary intents with the existing ones, and optionally with a
    model's. Blank and invalid labels are set aside, not counted."""
    if labels_file.get("sheet_id") != sheet_id(order):
        raise ValueError("these labels belong to a different sheet than the order file")
    unsure = {str(u) for u in labels_file.get("unsure", [])}
    invalid: list[dict[str, str]] = []
    unlabelled = 0
    rows: list[tuple[str, str, str, str]] = []  # (number, id, original, new)
    for number, item_id in enumerate(order, start=1):
        value = str(labels_file.get("labels", {}).get(str(number), "")).strip()
        if not value:
            unlabelled += 1
        elif value not in INTENTS:
            invalid.append({"number": str(number), "value": value})
        else:
            rows.append((str(number), item_id, golden[item_id]["labels"]["primary_intent"], value))
    exact = sum(orig == new for _, _, orig, new in rows)
    disagreements = [
        {"id": i, "original": o, "new": n, "unsure": num in unsure}
        for num, i, o, n in rows
        if o != n
    ]
    sure = [r for r in rows if r[0] not in unsure]
    flagged = [r for r in rows if r[0] in unsure]
    result: dict[str, Any] = {
        "labeller": labels_file.get("labeller", ""),
        "sheet_items": len(order),
        "unlabelled": unlabelled,
        "invalid": invalid,
        "agreement": {
            "n": len(rows),
            "exact": exact,
            "kappa": cohens_kappa([(o, n) for _, _, o, n in rows]),
        },
        "disagreements": disagreements,
        "confusion": dict(Counter(f"{d['original']} -> {d['new']}" for d in disagreements)),
        "unsure": {
            "n": len(flagged),
            "exact": sum(o == n for _, _, o, n in flagged),
            "sure_n": len(sure),
            "sure_exact": sum(o == n for _, _, o, n in sure),
        },
        "model": None,
    }
    if model is not None:
        both = [(model[i], o, n) for _, i, o, n in rows if i in model]
        wrong = [(m, o, n) for m, o, n in both if m != o]
        result["model"] = {
            "n": len(both),
            "vs_original": sum(m == o for m, o, _ in both),
            "vs_new": sum(m == n for m, _, n in both),
            "wrong_vs_original": len(wrong),
            "new_agrees_with_model": sum(n == m for m, _, n in wrong),
            "new_agrees_with_original": sum(n == o for _, o, n in wrong),
            "new_agrees_with_neither": sum(n != m and n != o for m, o, n in wrong),
            # Items whose label both labellers agree on: a score with less doubt about the label
            # in it (D-094).
            "agreed_n": sum(o == n for _, o, n in both),
            "agreed_right": sum(o == n == m for m, o, n in both),
        }
    return result


def percent(k: int, n: int) -> str:
    return f"{100 * k / n:.1f}%" if n else "n/a"


def render(result: dict[str, Any]) -> str:
    """A report of ids, labels and counts. It never holds message text."""
    a = result["agreement"]
    kappa = "n/a" if a["kappa"] is None else f"{a['kappa']:.2f}"
    u = result["unsure"]
    lines = [
        "# Intent label agreement",
        "",
        "> SYNTHETIC DATA. Ids, labels and counts only; no message text.",
        "",
        f"Second labeller: {result['labeller'] or '(not named)'}. "
        f"Sheet of {result['sheet_items']} items; {a['n']} labelled, "
        f"{result['unlabelled']} blank, {len(result['invalid'])} invalid.",
        "",
        f"- Exact agreement: {a['exact']} of {a['n']} ({percent(a['exact'], a['n'])})",
        f"- Cohen's kappa: {kappa}",
        f"- Items marked unsure: {u['n']}; agreement on those {u['exact']} of {u['n']}, "
        f"on the rest {u['sure_exact']} of {u['sure_n']}",
        "",
    ]
    if result["confusion"]:
        lines += ["## Disagreements by pair (existing label -> second labeller)", ""]
        lines += [f"- {pair}: {n}" for pair, n in sorted(result["confusion"].items())]
        lines += ["", "## Disagreements by item", ""]
        lines += [
            f"- {d['id']}: {d['original']} -> {d['new']}{' (unsure)' if d['unsure'] else ''}"
            for d in result["disagreements"]
        ]
        lines.append("")
    if result["invalid"]:
        lines += ["## Labels that are not an intent", ""]
        lines += [f"- sheet number {x['number']}: {x['value']!r}" for x in result["invalid"]]
        lines.append("")
    m = result["model"]
    if m:
        lines += [
            "## Against the model",
            "",
            f"Items both labelled and read by the model: {m['n']}.",
            "",
            f"- Model right against the existing label: {m['vs_original']} of {m['n']} "
            f"({percent(m['vs_original'], m['n'])})",
            f"- Model right against the second labeller: {m['vs_new']} of {m['n']} "
            f"({percent(m['vs_new'], m['n'])})",
            f"- Of the {m['wrong_vs_original']} items the model got wrong against the "
            "existing label:",
            f"  - the second labeller sides with the model: {m['new_agrees_with_model']} "
            "(doubt about the label)",
            "  - the second labeller sides with the existing label: "
            f"{m['new_agrees_with_original']} (model error)",
            f"  - the second labeller agrees with neither: {m['new_agrees_with_neither']} "
            "(the item is hard)",
            f"- On the {m['agreed_n']} items where both labellers agree, the model is right on "
            f"{m['agreed_right']} ({percent(m['agreed_right'], m['agreed_n'])})",
            "",
        ]
    lines += [
        "## What this cannot tell you",
        "",
        "- One extra labeller. Two people can agree and both be wrong, or differ on a rule that "
        "needs a decision.",
        "- The existing labels were written by the author of the system. The second labeller "
        "reads the rules cold.",
        "- A sample from the tuned and held-out splits, not the sealed set. The model was tuned on "
        "the tuned items, so its score against the existing labels is flattered there.",
        "",
    ]
    return "\n".join(lines)


# --- the command line ---


def _load_golden(path: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))["items"]
    return items


def _say(message: str) -> None:
    sys.stdout.write(message + "\n")


def _labelled(path: Path) -> bool:
    data = json.loads(path.read_text(encoding="utf-8"))
    return any(str(v).strip() for v in data.get("labels", {}).values())


def cmd_sheet(args: argparse.Namespace) -> int:
    labels_path = Path(args.labels_file)
    if labels_path.exists() and _labelled(labels_path):
        _say(f"{labels_path} already holds labels; move it aside first. Nothing was written.")
        return 1
    chosen = select_items(_load_golden(Path(args.golden)), args.n, args.seed)
    text, order = build_sheet(chosen)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / SHEET_NAME).write_text(text, encoding="utf-8")
    (out_dir / ORDER_NAME).write_text(json.dumps(order, indent=1) + "\n", encoding="utf-8")
    labels_path.parent.mkdir(parents=True, exist_ok=True)
    labels_path.write_text(json.dumps(label_template(order), indent=1) + "\n", encoding="utf-8")
    splits = Counter(i["split"] for i in chosen)
    _say(f"Sheet of {len(order)} items ({dict(sorted(splits.items()))}) -> {out_dir / SHEET_NAME}")
    _say(f"Fill in: {labels_path}")
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    golden = {i["id"]: i for i in _load_golden(Path(args.golden))}
    order_path = Path(args.order) if args.order else RUNS_DIR / ORDER_NAME
    order = json.loads(order_path.read_text(encoding="utf-8"))
    labels = json.loads(Path(args.labels_file).read_text(encoding="utf-8"))
    model = load_run_intents(Path(args.run)) if args.run else None
    text = render(score(golden, order, labels, model))
    if args.md:
        Path(args.md).write_text(text, encoding="utf-8")
        _say(f"Wrote {args.md}")
    else:
        _say(text)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    sub = parser.add_subparsers(dest="command", required=True)
    sheet = sub.add_parser("sheet", help="write a blind labelling sheet and an empty labels file")
    sheet.add_argument("--golden", default=str(GOLDEN_FILE))
    sheet.add_argument("--n", type=int, default=60)
    sheet.add_argument("--seed", type=int, default=0)
    sheet.add_argument("--out-dir", default=str(RUNS_DIR))
    sheet.add_argument("--labels-file", default=str(LABELS_FILE))
    sheet.set_defaults(func=cmd_sheet)
    scored = sub.add_parser("score", help="compare a filled labels file with the existing labels")
    scored.add_argument("--golden", default=str(GOLDEN_FILE))
    scored.add_argument("--labels-file", default=str(LABELS_FILE))
    scored.add_argument("--order", default=None, help="default: eval/runs/" + ORDER_NAME)
    scored.add_argument("--run", default=None, help="a saved run, to compare with the model")
    scored.add_argument("--md", default=None, help="write the report here instead of printing it")
    scored.set_defaults(func=cmd_score)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
