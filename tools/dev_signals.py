"""Measure the POLICY_EXCEPTION_REQUEST signal on a development set (D-074).

    python -m tools.dev_signals --mode main
    python -m tools.dev_signals --mode focused --md eval/reports/dev-policy-exception.md

Asks the real model (Ollama, loopback only) about each invented message in
`eval/dev/policy_exception_dev.json` and counts how many requests for an exception it flagged and
how many ordinary questions it flagged by mistake. Prints ids and counts, never message text. This
is a development measurement for choosing between prompts; it is not a result. The sealed set is
not used here and is never opened by this tool.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from citedesk import understand
from citedesk.config import Settings
from citedesk.models import ReasonCode
from citedesk.providers import LLMProvider

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILE = REPO_ROOT / "eval/dev/policy_exception_dev.json"


def load_items(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text("utf-8"))
    items: list[dict[str, Any]] = data["items"]
    return items


def score(items: list[dict[str, Any]], flagged: dict[str, bool]) -> dict[str, Any]:
    """`flagged[id]` is whether the model raised the signal. An item with no entry counts as not
    flagged (a failed read is a miss for a positive and a non-event for a negative)."""
    positives = [i for i in items if i["expect_exception"]]
    negatives = [i for i in items if not i["expect_exception"]]
    missed = [i["id"] for i in positives if not flagged.get(i["id"], False)]
    false_alarms = [i["id"] for i in negatives if flagged.get(i["id"], False)]
    return {
        "positives": len(positives),
        "negatives": len(negatives),
        "caught": len(positives) - len(missed),
        "false_alarms": len(false_alarms),
        "missed_ids": missed,
        "false_alarm_ids": false_alarms,
    }


def render(result: dict[str, Any], label: str) -> str:
    lines = [
        f"# Development set: POLICY_EXCEPTION_REQUEST signal, {label}",
        "",
        "> SYNTHETIC DATA. Development measurement, not a result. Ids and counts only.",
        "",
        f"- requests for an exception flagged: {result['caught']} of {result['positives']}",
        "- ordinary questions flagged by mistake: "
        f"{result['false_alarms']} of {result['negatives']}",
        f"- missed: {', '.join(result['missed_ids']) or 'none'}",
        f"- false alarms: {', '.join(result['false_alarm_ids']) or 'none'}",
    ]
    return "\n".join(lines) + "\n"


def collect(
    items: list[dict[str, Any]],
    llm: LLMProvider,
    *,
    mode: str,
    received_at: str,
    enable_thinking: bool,
) -> dict[str, bool]:
    """`mode` main: the signal from the main reading alone. `mode` focused: the one question."""
    flagged: dict[str, bool] = {}
    for item in items:
        try:
            if mode == "focused":
                asked, _ms = understand.asks_for_exception(
                    llm, subject=None, body=item["body"], enable_thinking=enable_thinking
                )
                flagged[item["id"]] = asked
            else:
                result = understand.understand(
                    llm,
                    subject=None,
                    body=item["body"],
                    received_at=received_at,
                    enable_thinking=enable_thinking,
                    exception_check=False,
                )
                flagged[item["id"]] = ReasonCode.POLICY_EXCEPTION_REQUEST in result.signals
        except understand.UnderstandFailed:
            continue
    return flagged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument("--mode", choices=("main", "focused"), default="focused")
    parser.add_argument("--file", default=str(DEFAULT_FILE))
    parser.add_argument("--thinking", choices=("on", "off"), default=None)
    parser.add_argument("--md", help="write the summary here")
    args = parser.parse_args(argv)

    from citedesk.providers.ollama import OllamaProvider

    settings = Settings()
    llm = OllamaProvider.from_settings(settings)
    data = json.loads(Path(args.file).read_text("utf-8"))
    items: list[dict[str, Any]] = data["items"]
    thinking = settings.enable_thinking if args.thinking is None else args.thinking == "on"
    flagged = collect(
        items,
        llm,
        mode=args.mode,
        received_at=f"{data['reference_date']}T12:00:00Z",
        enable_thinking=thinking,
    )
    label = f"{args.mode} question, thinking {'on' if thinking else 'off'}"
    text = render(score(items, flagged), label)
    if args.md:
        Path(args.md).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
