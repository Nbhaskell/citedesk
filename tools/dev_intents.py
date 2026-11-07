"""Measure the primary intent on a development set (D-085).

    python -m tools.dev_intents --set hours --md eval/reports/dev-hours-availability.md

Asks the real model (Ollama, loopback only) to read each invented message in `eval/dev/` and counts
how many get the expected primary intent. Prints ids, intent names and counts, never message text.
This is a development measurement for choosing between designs; it is not a result. The sealed
set is not used here and is never opened by this tool.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from citedesk import understand
from citedesk.config import Settings
from citedesk.providers import LLMProvider

REPO_ROOT = Path(__file__).resolve().parent.parent
SETS = {
    "hours": REPO_ROOT / "eval/dev/hours_availability_dev.json",
    "spam": REPO_ROOT / "eval/dev/spam_dev.json",
}


def load_items(path: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = json.loads(path.read_text("utf-8"))["items"]
    return items


def score(items: list[dict[str, Any]], read: dict[str, str | None]) -> dict[str, Any]:
    """`read[id]` is the primary intent the model gave. An item with no entry was not read (the
    model failed) and counts as a miss."""
    misses: dict[str, str | None] = {}
    by_expected: dict[str, dict[str, int]] = {}
    correct = 0
    for item in items:
        row = by_expected.setdefault(item["expect_primary"], {"correct": 0, "total": 0})
        row["total"] += 1
        got = read.get(item["id"])
        if got == item["expect_primary"]:
            row["correct"] += 1
            correct += 1
        else:
            misses[item["id"]] = got
    return {
        "correct": correct,
        "total": len(items),
        "misses": misses,
        "by_expected": by_expected,
    }


def render(result: dict[str, Any], label: str) -> str:
    lines = [
        f"# Development set: {label}",
        "",
        "> SYNTHETIC DATA. Development measurement, not a result. Ids and counts only.",
        "",
        f"- expected primary intent: {result['correct']} of {result['total']}",
    ]
    for name, row in sorted(result["by_expected"].items()):
        lines.append(f"- expected {name}: {row['correct']} of {row['total']}")
    for item_id, got in result["misses"].items():
        lines.append(f"- {item_id}: {'read as ' + got if got else 'not read'}")
    return "\n".join(lines) + "\n"


def collect(
    items: list[dict[str, Any]], llm: LLMProvider, *, received_at: str, enable_thinking: bool
) -> dict[str, str | None]:
    read: dict[str, str | None] = {}
    for item in items:
        try:
            result = understand.understand(
                llm,
                subject=None,
                body=item["body"],
                received_at=received_at,
                enable_thinking=enable_thinking,
                focused_checks=False,
            )
        except understand.UnderstandFailed:
            continue
        read[item["id"]] = result.output.primary_intent.value
    return read


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument("--set", dest="which", choices=tuple(SETS), default="hours")
    parser.add_argument("--thinking", choices=("on", "off"), default=None)
    parser.add_argument("--md", help="write the summary here")
    args = parser.parse_args(argv)

    data = json.loads(SETS[args.which].read_text("utf-8"))
    settings = Settings()
    from citedesk.providers.ollama import OllamaProvider

    llm = OllamaProvider.from_settings(settings)
    thinking = settings.enable_thinking if args.thinking is None else args.thinking == "on"
    read = collect(
        data["items"],
        llm,
        received_at=f"{data['header']['reference_date']}T12:00:00Z",
        enable_thinking=thinking,
    )
    text = render(
        score(data["items"], read), f"{args.which}, thinking {'on' if thinking else 'off'}"
    )
    if args.md:
        Path(args.md).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
