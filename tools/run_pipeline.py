"""Run the tuned split through the whole pipeline (screen to check) and write a reading sheet.

Run (needs Ollama and rag-project; see CLAUDE.md):
    python -m tools.run_pipeline                    run all tuned items, summarise, write the sheet
    python -m tools.run_pipeline --sheet 30         how many drafts the reading sheet holds
    python -m tools.run_pipeline --limit 10         only the first 10 items (a check, not a result)

Phase 5 task 6: read 30 drafts and write down what looks wrong. The run file and the sheet go in
`eval/runs/` (git-ignored). They hold the system's drafts and the synthetic messages they answer,
so they are for reading, not for publishing. The scored evaluation is Phase 7.
"""

import argparse
import sys
import time
from collections import Counter
from typing import Any

from citedesk.business import load_business
from citedesk.config import Settings
from citedesk.knowledge import RagProjectKB
from citedesk.providers.ollama import OllamaProvider
from tools.golden import GOLDEN_FILE
from tools.score_understanding import RUNS_DIR, load_golden, make_run, write_json


def summarise(run: dict[str, Any]) -> str:
    records = run["items"]
    statuses = Counter(r["status"] for r in records)
    kinds = Counter(r["draft"]["kind"] for r in records if r.get("draft"))
    drafts = [r for r in records if r.get("draft")]
    passed: Counter[str] = Counter()
    failed: Counter[str] = Counter()
    for record in drafts:
        for check in record["checks"]:
            (passed if check["passed"] else failed)[check["code"]] += 1
    ungrounded = sum(
        len(c["detail"].get("ungrounded", []))
        for r in drafts
        for c in r["checks"]
        if c["code"] == "FIGURES_GROUNDED"
    )
    ready = sum(1 for r in drafts if r["draft"]["status"] == "ready")
    lines = [
        f"Run {run['header']['run_id']}: {len(records)} items",
        f"  status          {dict(statuses)}",
        f"  drafts          {len(drafts)} ({dict(kinds)}), ready {ready}, "
        f"blocked {len(drafts) - ready}",
        "  checks (passed / failed over all drafts)",
    ]
    for code in sorted(set(passed) | set(failed)):
        lines.append(f"    {code:<22} {passed[code]:>3} / {failed[code]:<3}")
    lines.append(f"  ungrounded figures found by the figure check: {ungrounded}")
    escalated_by_check = [
        r["id"] for r in records if any(e["source"] == "check" for e in r["reasons"])
    ]
    lines.append(f"  escalated by a check: {len(escalated_by_check)} {escalated_by_check}")
    lines.append(f"  failed: {[r['id'] for r in records if r['status'] == 'failed']}")
    return "\n".join(lines)


def reading_sheet(run: dict[str, Any], items: dict[str, dict[str, Any]], count: int) -> str:
    """Markdown with `count` drafts spread evenly across the run, each beside what it answers."""
    drafted = [r for r in run["items"] if r.get("draft")]
    step = max(1, len(drafted) // max(1, count))
    chosen = drafted[::step][:count]
    out = [
        "# Draft reading sheet",
        "",
        "SYNTHETIC DATA. Every customer and message here is invented.",
        f"Run {run['header']['run_id']}; {len(chosen)} of {len(drafted)} drafts.",
        "",
    ]
    for number, record in enumerate(chosen, start=1):
        item = items[record["id"]]
        draft = record["draft"]
        out += [
            f"## {number}. {record['id']}",
            f"category `{item['category']}` | label route `{item['labels']['expected_route']}` | "
            f"got `{record['route']}` / status `{record['status']}` | draft `{draft['kind']}` "
            f"`{draft['status']}` (model {draft['model']})",
            "",
            f"**Customer** ({item['labels']['primary_intent']}): "
            f"{item.get('subject') or '(no subject)'}",
            "",
            *[f"> {line}" for line in item["body"].splitlines()],
            "",
            "**Asked the knowledge base:**",
            *[
                f"- {r['question']} -> {'declined' if r['declined'] else 'answered'}: "
                + ", ".join(f"{s['file']} ({s['section']})" for s in r["sources"])
                for r in record["retrievals"]
            ],
            "",
            f"**Draft** - subject: {draft['subject']}",
            "",
            *[f"    {line}" for line in draft["body"].splitlines()],
            "",
            "Claims: " + "; ".join(f"[{c['source_index']}] {c['text']}" for c in draft["claims"]),
            "Checks: "
            + ", ".join(f"{c['code']}={'ok' if c['passed'] else 'FAIL'}" for c in record["checks"]),
            "",
            "Notes:",
            "",
        ]
    return "\n".join(out)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument("--split", default="tuned", help="only 'tuned' can be run here")
    parser.add_argument("--limit", type=int, help="run only the first N items (not a result)")
    parser.add_argument("--sheet", type=int, default=30, help="drafts on the reading sheet")
    args = parser.parse_args(argv)
    if args.split != "tuned":
        print(
            "The held-out split is run once, in Phase 7, and never used to tune. "
            "This script runs the tuned split only.",
            file=sys.stderr,
        )
        return 2

    golden = load_golden()
    items = [i for i in golden["items"] if i["split"] == args.split]
    if args.limit:
        items = items[: args.limit]
    settings = Settings()
    llm = OllamaProvider.from_settings(settings)
    began = time.monotonic()

    def progress(number: int, total: int, record: dict[str, Any]) -> None:
        print(
            f"[{number}/{total}] {record['id']}: {record['status']} "
            f"({time.monotonic() - began:.0f}s elapsed)",
            file=sys.stderr,
        )

    run = make_run(
        items,
        settings,
        llm,
        split=args.split,
        reference_date=golden["header"]["reference_date"],
        progress=progress,
        kb=RagProjectKB(settings.rag_url),
        business=load_business(settings.business_facts_path),
        with_drafts=True,
    )
    run["header"]["stages"] = ["screen", "understand", "route", "retrieve", "draft", "check"]
    run["header"]["run_id"] = run["header"]["run_id"].replace("understand-v1", "pipeline-v1")
    base = RUNS_DIR / run["header"]["run_id"]
    write_json(base.with_suffix(".drafts.json"), run)
    by_id = {i["id"]: i for i in golden["items"]}
    sheet = base.with_suffix(".sheet.md")
    sheet.write_text(reading_sheet(run, by_id, args.sheet), encoding="utf-8", newline="\n")
    print(summarise(run))
    print(f"\nWrote {base.with_suffix('.drafts.json').name} and {sheet.name} in {RUNS_DIR}")
    print(f"Golden file: {GOLDEN_FILE.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
