"""Compare two settings of one system (for example thinking on and off) over several passes each.

    python -m tools.eval_compare --a RUN1 RUN2 RUN3 --b RUN4 RUN5 RUN6 \\
        --label-a think-off --label-b think-on --md eval/reports/thinking.md

Both groups must be runs of the same code, model, prompts, knowledge base and split; only a setting
may differ. A difference in a headline measure is called **real** only if it is larger than the 95%
t-interval from the spread between passes AND a paired bootstrap over items excludes zero. Meeting
one of the two is **unclear**, not "no effect", and the report says how large a difference the test
could have seen (D-062; qa-eval-harness step 6).

The held-out split is never used to choose between settings (D-061): this refuses it.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from tools import eval_common as ec
from tools import eval_score as es
from tools import eval_stats as stats

SAME_KEYS = ("split", "split_sha256", "limit", "model", "prompt_versions")


def _header(one: dict[str, Any]) -> dict[str, Any]:
    header: dict[str, Any] = one["run"]["header"]
    return header


def _within(group: list[dict[str, Any]]) -> list[str]:
    """Why the passes in a group are not passes of one system (empty if they are)."""
    out: list[str] = []
    for one in group[1:]:
        a, b = _header(group[0]), _header(one)
        for key in (*SAME_KEYS, "settings"):
            if a.get(key) != b.get(key):
                out.append(key)
        if (a.get("git") or {}).get("code_tree") != (b.get("git") or {}).get("code_tree"):
            out.append("code_tree")
        if ec.rag_identity(a.get("rag") or {}) != ec.rag_identity(b.get("rag") or {}):
            out.append("rag")
    return sorted(set(out))


def setting_differences(
    a: list[dict[str, Any]], b: list[dict[str, Any]]
) -> dict[str, tuple[Any, Any]]:
    sa, sb = _header(a[0]).get("settings") or {}, _header(b[0]).get("settings") or {}
    return {k: (sa.get(k), sb.get(k)) for k in sorted(set(sa) | set(sb)) if sa.get(k) != sb.get(k)}


def problems(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> list[str]:
    """Reasons these two groups cannot be compared (empty if they can)."""
    found: list[str] = []
    for name, group in (("first", a), ("second", b)):
        if not group:
            found.append(f"the {name} group has no runs")
    if found:
        return found
    if any(_header(one).get("split") in ec.LOCKED_SPLITS for one in [*a, *b]):
        found.append(
            "held-out and sealed runs cannot be compared: their results are not used to choose "
            "between settings (D-061, D-071); make the choice on the tuned split"
        )
    for name, group in (("first", a), ("second", b)):
        why = _within(group)
        if why:
            found.append(f"within the {name} group the runs differ in {', '.join(why)}")
    if found:
        return found
    ha, hb = _header(a[0]), _header(b[0])
    other = [key for key in SAME_KEYS if ha.get(key) != hb.get(key)]
    if (ha.get("git") or {}).get("code_tree") != (hb.get("git") or {}).get("code_tree"):
        other.append("code_tree")
    if ec.rag_identity(ha.get("rag") or {}) != ec.rag_identity(hb.get("rag") or {}):
        other.append("rag")
    if other:
        found.append(f"the groups differ in more than a setting: {', '.join(other)}")
    if not setting_differences(a, b):
        found.append("no setting differs between the groups, so there is nothing to compare")
    return found


def compare_groups(
    a: list[dict[str, Any]], b: list[dict[str, Any]], *, resamples: int = 10_000, seed: int = 0
) -> dict[str, Any]:
    return stats.compare(
        [one["vectors"] for one in a],
        [one["vectors"] for one in b],
        resamples=resamples,
        seed=seed,
    )


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{100 * value:.1f}%"


def _pp(value: float | None) -> str:
    return "n/a" if value is None else f"{100 * value:+.1f} pp"


def compare_markdown(
    label_a: str,
    label_b: str,
    a: list[dict[str, Any]],
    b: list[dict[str, Any]],
    result: dict[str, Any],
) -> str:
    differences = setting_differences(a, b)
    lines = [
        f"# Comparison: {label_a} against {label_b}",
        "",
        "> SYNTHETIC DATA. Every customer and message here is invented.",
        "",
        f"- {label_a}: {len(a)} passes; {label_b}: {len(b)} passes; split "
        f"`{_header(a[0]).get('split')}`, hash `{str(_header(a[0]).get('split_sha256'))[:12]}`",
        "- the setting that differs: "
        + (", ".join(f"{k} = {x} against {y}" for k, (x, y) in differences.items()) or "none"),
        "",
        "A difference is **real** only if it is larger than the 95% t-interval from the spread "
        "between passes **and** a paired bootstrap over items (resampling the same items for both "
        "settings) excludes zero. Meeting only one is **unclear**, which is not the same as no "
        "effect. Differences are in percentage points, first minus second.",
        "",
        f"| Measure | {label_a} (mean, ±95%) | {label_b} (mean, ±95%) | Difference | "
        "Pass interval ± | Bootstrap 95% | Call |",
        "|---|---|---|---|---|---|---|",
    ]
    for name in es.MEASURES:
        row = result[name]
        boot = row["bootstrap"]
        call = row["verdict"]["call"]
        if call == "real":
            call = f"real ({label_a if row['verdict']['higher'] == 'a' else label_b} higher)"
        lines.append(
            f"| {name} | {_pct(row['a']['mean'])} ± {_pct(row['a']['half_width_95'])} | "
            f"{_pct(row['b']['mean'])} ± {_pct(row['b']['half_width_95'])} | {_pp(row['diff'])} | "
            f"{_pct(row['pass_interval_half_width'])} | "
            f"{_pp(boot['ci_low'])} to {_pp(boot['ci_high'])} | {call} |"
        )
    lines += ["", "## What the test could have seen", ""]
    for name in es.MEASURES:
        row = result[name]
        verdict = row["verdict"]
        size = verdict["smallest_detectable"]
        lines.append(
            f"- {name}: {verdict['call']}; {verdict['why']}."
            + (f" Differences under about {_pp(size)} could not have been seen." if size else "")
            + (f" Note: {verdict['note']}." if verdict["note"] else "")
        )
    lines += [
        "",
        "## What this cannot tell you",
        "",
        "- The passes use a fixed seed, so run-to-run spread may be small for reasons that do not "
        "hold on another machine or with another seed; a zero spread leaves the call to the "
        "bootstrap alone.",
        "- The bootstrap resamples these items. It says nothing about customers who write "
        "differently, and one labeller wrote every label.",
        "- Health-and-safety recall rests on a handful of items, so it can only show a large "
        "difference.",
        "- Thinking applies to the understand step only here; rag-project's own thinking setting "
        "is recorded in each run and was the same in both groups.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument(
        "--a", nargs="+", type=Path, required=True, help="runs of the first setting"
    )
    parser.add_argument(
        "--b", nargs="+", type=Path, required=True, help="runs of the second setting"
    )
    parser.add_argument("--label-a", default="A")
    parser.add_argument("--label-b", default="B")
    parser.add_argument("--md", type=Path, help="write the Markdown report here")
    parser.add_argument("--json", type=Path, help="write the numbers here")
    parser.add_argument("--resamples", type=int, default=10_000)
    args = parser.parse_args(argv)

    # Read only the splits the runs were made on; refuse before reading labels if held-out.
    headers = [json.loads(p.read_text("utf-8"))["header"] for p in [*args.a, *args.b]]
    if any(h.get("split") in ec.LOCKED_SPLITS for h in headers):
        print("Refused: " + problems_for_heldout(), file=sys.stderr)
        return 2
    golden = json.loads(ec.GOLDEN_FILE.read_text("utf-8"))
    a = [es.load_pass(p, golden) for p in args.a]
    b = [es.load_pass(p, golden) for p in args.b]
    found = problems(a, b)
    if found:
        for problem in found:
            print(f"Refused: {problem}", file=sys.stderr)
        return 2
    result = compare_groups(a, b, resamples=args.resamples)
    text = compare_markdown(args.label_a, args.label_b, a, b, result)
    if args.md:
        args.md.parent.mkdir(parents=True, exist_ok=True)
        args.md.write_text(text, encoding="utf-8", newline="\n")
    if args.json:
        ec.write_json_atomic(args.json, {"labels": [args.label_a, args.label_b], "result": result})
    print(text)
    return 0


def problems_for_heldout() -> str:
    return (
        "held-out and sealed runs cannot be compared: their results are not used to choose "
        "between settings (D-061, D-071); make the choice on the tuned split"
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
