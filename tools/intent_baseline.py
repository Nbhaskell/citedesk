"""An intent baseline that uses no model (D-093).

Why. Primary-intent accuracy for `qwen3:8b` is reported against a target, but not against a cheap
method. A baseline shows how much the language model adds: if word counts get close, the model is
not earning its cost on this step.

Two baselines, both plain code with no settings to tune:
- **Majority:** always answer the commonest primary intent of the training items.
- **Naive Bayes:** multinomial, on lower-case words and pairs of neighbouring words from the subject
  and body, add-one smoothing. Ties go to the intent that sorts first.

Trained on the tuned split, scored once on the held-out split. Leave-one-out on the tuned split is
reported as well. The sealed split is refused. Nothing is tuned: the method and its features were
fixed before the held-out score was seen.

    python -m tools.intent_baseline [--run eval/runs/<held-out run>.run.json ...] [--md PATH]

`--run` adds a paired comparison with a saved model run on the same held-out items. Reports hold
ids, intents and counts only: no message text.
"""

import argparse
import json
import math
import re
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

from tools.golden import GOLDEN_FILE
from tools.label_agreement import load_run_intents

WORD = re.compile(r"[a-z0-9']+")


def features(text: str) -> list[str]:
    """Lower-case words, then each pair of neighbouring words."""
    words = WORD.findall(text.lower())
    return words + [f"{a} {b}" for a, b in zip(words, words[1:], strict=False)]


def text_of(item: dict[str, Any]) -> str:
    return f"{item.get('subject') or ''}\n{item['body']}"


def primary(item: dict[str, Any]) -> str:
    return str(item["labels"]["primary_intent"])


class Classifier(Protocol):
    def predict(self, text: str) -> str: ...


class Majority:
    def __init__(self, answer: str) -> None:
        self.answer = answer

    @classmethod
    def fit(cls, items: Sequence[dict[str, Any]]) -> "Majority":
        counts = Counter(primary(i) for i in items)
        return cls(min(counts, key=lambda intent: (-counts[intent], intent)))

    def predict(self, text: str) -> str:
        return self.answer


class NaiveBayes:
    def __init__(
        self, priors: dict[str, float], counts: dict[str, Counter[str]], vocabulary: set[str]
    ) -> None:
        self.priors = priors
        self.counts = counts
        self.totals = {intent: sum(c.values()) for intent, c in counts.items()}
        self.vocabulary = vocabulary

    @classmethod
    def fit(cls, items: Sequence[dict[str, Any]]) -> "NaiveBayes":
        per_intent = Counter(primary(i) for i in items)
        counts: dict[str, Counter[str]] = {intent: Counter() for intent in per_intent}
        for i in items:
            counts[primary(i)].update(features(text_of(i)))
        vocabulary = {word for c in counts.values() for word in c}
        priors = {intent: math.log(n / len(items)) for intent, n in per_intent.items()}
        return cls(priors, counts, vocabulary)

    def predict(self, text: str) -> str:
        known = [f for f in features(text) if f in self.vocabulary]
        size = len(self.vocabulary)

        def score(intent: str) -> float:
            total = self.totals[intent] + size
            return self.priors[intent] + sum(
                math.log((self.counts[intent][f] + 1) / total) for f in known
            )

        return min(self.priors, key=lambda intent: (-score(intent), intent))


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n == 0:
        return None, None
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def evaluate(model: Classifier, items: Sequence[dict[str, Any]]) -> dict[str, Any]:
    predictions = {i["id"]: model.predict(text_of(i)) for i in items}
    confusion: Counter[str] = Counter()
    correct = 0
    for i in items:
        if predictions[i["id"]] == primary(i):
            correct += 1
        else:
            confusion[f"{primary(i)} -> {predictions[i['id']]}"] += 1
    return {
        "n": len(items),
        "correct": correct,
        "confusion": dict(sorted(confusion.items(), key=lambda kv: (-kv[1], kv[0]))),
        "predictions": predictions,
    }


def leave_one_out(kind: Any, items: Sequence[dict[str, Any]]) -> dict[str, Any]:
    correct = 0
    for index, held in enumerate(items):
        model = kind.fit([i for j, i in enumerate(items) if j != index])
        correct += model.predict(text_of(held)) == primary(held)
    return {"n": len(items), "correct": correct}


def paired(gold: dict[str, str], baseline: dict[str, str], model: dict[str, str]) -> dict[str, int]:
    """On the items the model read: who got each one right."""
    ids = [i for i in gold if i in model and i in baseline]
    tally = Counter()
    for i in ids:
        m, b = model[i] == gold[i], baseline[i] == gold[i]
        tally["both_right" if m and b else "model_only" if m else "baseline_only" if b else
              "both_wrong"] += 1  # fmt: skip
    return {
        "n": len(ids),
        "both_right": tally["both_right"],
        "model_only": tally["model_only"],
        "baseline_only": tally["baseline_only"],
        "both_wrong": tally["both_wrong"],
        "model_correct": tally["both_right"] + tally["model_only"],
        "baseline_correct": tally["both_right"] + tally["baseline_only"],
    }


def split_items(
    items: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if any(i.get("split") == "sealed" for i in items):
        raise ValueError("a sealed item was given; the sealed set is never used here")
    return (
        [i for i in items if i.get("split") == "tuned"],
        [i for i in items if i.get("split") == "heldout"],
    )


def percent(k: int, n: int) -> str:
    if n == 0:
        return "n/a"
    low, high = wilson(k, n)
    if low is None or high is None:
        return "n/a"
    return f"{k} of {n} ({100 * k / n:.1f}%; 95% interval {100 * low:.1f}% to {100 * high:.1f}%)"


def render(result: dict[str, Any]) -> str:
    lines = [
        "# Intent baseline without a model",
        "",
        "> SYNTHETIC DATA. Ids, intents and counts only; no message text.",
        "",
        f"Trained on the tuned split ({result['n_train']} items), scored once on the held-out "
        f"split ({result['n_test']} items). Primary intent only. Method fixed before scoring "
        "(D-093).",
        "",
        "| Method | Held-out | Tuned, leave-one-out |",
        "|---|---|---|",
    ]
    for name in ("Majority", "Naive Bayes"):
        held, loo = result[name]["heldout"], result[name]["loo"]
        lines.append(
            f"| {name} | {percent(held['correct'], held['n'])} | "
            f"{percent(loo['correct'], loo['n'])} |"
        )
    lines += [
        "",
        f"Majority answer: `{result['majority_answer']}`. Leave-one-out is a poor guide for the "
        "majority method: when two intents are nearly as common, leaving one item out can change "
        "the answer to the other intent, so the method is wrong on every item. Read its held-out "
        "column.",
        "",
    ]
    lines += ["## Naive Bayes errors on the held-out split (label -> baseline)", ""]
    lines += [f"- {pair}: {n}" for pair, n in result["Naive Bayes"]["heldout"]["confusion"].items()]
    for run in result.get("runs", []):
        p = run["paired"]
        lines += [
            "",
            f"## Paired with model run `{run['name']}`",
            "",
            f"Items both answered: {p['n']}.",
            f"- Model right: {percent(p['model_correct'], p['n'])}",
            f"- Naive Bayes right: {percent(p['baseline_correct'], p['n'])}",
            f"- Both right {p['both_right']}, model only {p['model_only']}, "
            f"baseline only {p['baseline_only']}, both wrong {p['both_wrong']}",
        ]
    caveat = (
        "- The test items come from another file (`--test-golden`), such as another business's "
        "set, while training and leave-one-out stay on the tuned items of `--golden`. Words that "
        "belong to one trade do not carry to another, which costs a word-count method more than "
        "the prompts."
        if result.get("other_test_file")
        else "- The held-out set is small and was written by the same author as the tuned set, so "
        "shared wording helps a word-count method as much as it helps the prompts."
    )
    lines += [
        "",
        "## What this cannot tell you",
        "",
        caveat,
        "- A saved model run is of the system as it was when that run was made.",
        "- Primary intent only; routing, escalation and drafting are not compared.",
        "",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--golden", type=Path, default=GOLDEN_FILE)
    parser.add_argument("--run", type=Path, action="append", default=[])
    parser.add_argument("--md", type=Path)
    parser.add_argument(
        "--test-golden",
        type=Path,
        help="score on the held-out items of another file, such as another business's set; "
        "training stays on --golden's tuned items (D-100)",
    )
    args = parser.parse_args(argv)

    items = json.loads(args.golden.read_text(encoding="utf-8"))["items"]
    train, test = split_items(items)
    if args.test_golden:
        _, test = split_items(json.loads(args.test_golden.read_text(encoding="utf-8"))["items"])
    result: dict[str, Any] = {
        "n_train": len(train),
        "n_test": len(test),
        "other_test_file": bool(args.test_golden),
    }
    for name, kind in (("Majority", Majority), ("Naive Bayes", NaiveBayes)):
        result[name] = {
            "heldout": evaluate(kind.fit(train), test),
            "loo": leave_one_out(kind, train),
        }
    result["majority_answer"] = Majority.fit(train).answer
    gold = {i["id"]: primary(i) for i in test}
    baseline = result["Naive Bayes"]["heldout"]["predictions"]
    result["runs"] = [
        {"name": run.name, "paired": paired(gold, baseline, load_run_intents(run))}
        for run in args.run
    ]
    text = render(result)
    if args.md:
        args.md.parent.mkdir(parents=True, exist_ok=True)
        args.md.write_text(text, encoding="utf-8")
        print(f"Wrote {args.md}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
