"""Measure the exception and injection signals on development sets (D-074, D-075).

    python -m tools.dev_signals --set exception --md eval/reports/dev-policy-exception.md
    python -m tools.dev_signals --set injection --md eval/reports/dev-injection.md
    python -m tools.dev_signals --set injection --mode patterns       no model: screening only

Asks the real model (Ollama, loopback only) about each invented message in `eval/dev/` and counts
the instructions or exception requests it flagged and the ordinary messages it flagged by mistake.
Prints ids and counts, never message text. This is a development measurement for choosing between
designs; it is not a result. The sealed set is not used here and is never opened by this tool.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from citedesk import understand
from citedesk.config import Settings
from citedesk.providers import LLMProvider
from citedesk.screening import injection_flags

REPO_ROOT = Path(__file__).resolve().parent.parent
SETS = {
    "exception": (REPO_ROOT / "eval/dev/policy_exception_dev.json", "expect_exception"),
    "injection": (REPO_ROOT / "eval/dev/injection_dev.json", "expect_injection"),
}
DEFAULT_FILE = SETS["exception"][0]


def load_items(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text("utf-8"))
    items: list[dict[str, Any]] = data["items"]
    return items


def score(
    items: list[dict[str, Any]], flagged: dict[str, bool], key: str = "expect_exception"
) -> dict[str, Any]:
    """`flagged[id]` is whether the signal was raised. An item with no entry counts as not
    flagged (a failed read is a miss for a positive and a non-event for a negative). Items with a
    `batch` are also counted per batch."""
    positives = [i for i in items if i[key]]
    negatives = [i for i in items if not i[key]]
    missed = [i["id"] for i in positives if not flagged.get(i["id"], False)]
    false_alarms = [i["id"] for i in negatives if flagged.get(i["id"], False)]
    batches: dict[str, dict[str, int]] = {}
    for item in items:
        batch = item.get("batch")
        if batch is None:
            continue
        row = batches.setdefault(batch, {"positives": 0, "caught": 0, "negatives": 0, "false": 0})
        on = flagged.get(item["id"], False)
        if item[key]:
            row["positives"] += 1
            row["caught"] += on
        else:
            row["negatives"] += 1
            row["false"] += on
    return {
        "positives": len(positives),
        "negatives": len(negatives),
        "caught": len(positives) - len(missed),
        "false_alarms": len(false_alarms),
        "missed_ids": missed,
        "false_alarm_ids": false_alarms,
        "batches": batches,
    }


def render(result: dict[str, Any], label: str) -> str:
    lines = [
        f"# Development set: {label}",
        "",
        "> SYNTHETIC DATA. Development measurement, not a result. Ids and counts only.",
        "",
        f"- flagged correctly: {result['caught']} of {result['positives']}",
        "- ordinary messages flagged by mistake: "
        f"{result['false_alarms']} of {result['negatives']}",
        f"- missed: {', '.join(result['missed_ids']) or 'none'}",
        f"- false alarms: {', '.join(result['false_alarm_ids']) or 'none'}",
    ]
    for batch, row in sorted(result["batches"].items()):
        lines.append(
            f"- batch {batch}: flagged {row['caught']} of {row['positives']}; "
            f"by mistake {row['false']} of {row['negatives']}"
        )
    return "\n".join(lines) + "\n"


def collect(
    items: list[dict[str, Any]],
    llm: LLMProvider | None,
    *,
    which: str,
    mode: str,
    received_at: str,
    enable_thinking: bool,
) -> dict[str, bool]:
    """`which` is the signal; `mode` is `focused` (the two questions), `main` (the main reading
    alone, exception only) or `patterns` (screening only, injection only; no model)."""
    flagged: dict[str, bool] = {}
    for item in items:
        if mode == "patterns":
            flagged[item["id"]] = bool(injection_flags(item["body"]))
            continue
        if llm is None:
            raise ValueError("this mode needs a model")
        try:
            if mode == "focused":
                answers, _ms = understand.ask_focused(
                    llm, subject=None, body=item["body"], enable_thinking=enable_thinking
                )
                flagged[item["id"]] = (
                    answers.asks_for_exception
                    if which == "exception"
                    else answers.addresses_the_assistant
                )
            else:
                result = understand.understand(
                    llm,
                    subject=None,
                    body=item["body"],
                    received_at=received_at,
                    enable_thinking=enable_thinking,
                    focused_checks=False,
                )
                names = {code.value for code in result.signals}
                flagged[item["id"]] = "POLICY_EXCEPTION_REQUEST" in names
        except understand.UnderstandFailed:
            continue
    return flagged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument("--set", dest="which", choices=tuple(SETS), default="exception")
    parser.add_argument("--mode", choices=("focused", "main", "patterns"), default="focused")
    parser.add_argument("--thinking", choices=("on", "off"), default=None)
    parser.add_argument("--md", help="write the summary here")
    args = parser.parse_args(argv)
    if args.mode == "main" and args.which != "exception":
        parser.error("--mode main measures the exception signal only")
    if args.mode == "patterns" and args.which != "injection":
        parser.error("--mode patterns measures the injection signal only")

    path, key = SETS[args.which]
    data = json.loads(path.read_text("utf-8"))
    items: list[dict[str, Any]] = data["items"]
    settings = Settings()
    llm: LLMProvider | None = None
    if args.mode != "patterns":
        from citedesk.providers.ollama import OllamaProvider

        llm = OllamaProvider.from_settings(settings)
    thinking = settings.enable_thinking if args.thinking is None else args.thinking == "on"
    flagged = collect(
        items,
        llm,
        which=args.which,
        mode=args.mode,
        received_at=f"{data['reference_date']}T12:00:00Z",
        enable_thinking=thinking,
    )
    label = f"{args.which} signal, {args.mode}"
    if args.mode != "patterns":
        label += f", thinking {'on' if thinking else 'off'}"
    text = render(score(items, flagged, key), label)
    if args.md:
        Path(args.md).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
