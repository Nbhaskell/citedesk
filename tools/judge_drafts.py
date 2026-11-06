"""Score Citedesk's drafts with citeCheck's judge, and check the judge itself (D-079).

    python -m tools.judge_drafts judge                     faithfulness of every saved model draft
    python -m tools.judge_drafts known-bad --judged FILE   does the judge notice damage we add?
    python -m tools.judge_drafts sheet --judged FILE       a blind sheet for labelling by hand
    python -m tools.judge_drafts calibrate --judged FILE   the judge against those hand labels

citeCheck (the sibling project: the `citeCheck` folder next to this repository, or
`--citecheck PATH` or `CITECHECK_SRC`) is read from its source folder and not installed.
This tool imports its `Judge` (`qwen3:8b` through Ollama on this machine, thinking on,
temperature 0) and nothing else. It is an optional measurement: the tests use a scripted judge
and need neither citeCheck nor a model.

The question the judge asks is citeCheck's faithfulness one: is every claim in the draft backed by
the passages it was written from? It does not ask whether the draft is correct or helpful, and it
cannot see what the passages leave out. A draft's greeting and sign-off are removed first.

Saved files hold the synthetic messages and drafts, so they go to `eval/runs/` (git-ignored).
What is printed is counts and ids, never text (rule 4). Hand labels are ids and labels only and
may be committed (`eval/labels/`).
"""

import argparse
import glob
import json
import random
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from citedesk.drafting import compose_body
from citedesk.models import Source
from tools.golden import GOLDEN_FILE, REPO_ROOT

RUNS_DIR = REPO_ROOT / "eval/runs"
LABELS_DIR = REPO_ROOT / "eval/labels"
PLANTS_FILE = REPO_ROOT / "eval/dev/planted_sentences_dev.json"
DEFAULT_CITECHECK = REPO_ROOT.parent / "citeCheck" / "src"
VERDICTS = ("supported", "partly_supported", "unsupported")
SCORE = {"supported": 1.0, "partly_supported": 0.5, "unsupported": 0.0}
LOOPBACK = ("127.0.0.1", "localhost", "::1")

Case = dict[str, Any]


class JudgeLike(Protocol):
    def verdict(self, kind: str, **fields: Any) -> dict[str, Any]: ...


# --- the cases ---


def _merged(sources: list[dict[str, Any]], seen: list[Source]) -> None:
    for raw in sources:
        source = Source(**raw)
        if source not in seen:
            seen.append(source)


def middle_of(body: str) -> str:
    """The draft without its greeting and sign-off, as the judge should read it."""
    laid_out = compose_body(_NO_BUSINESS, sender_name=None, model_body=body)
    parts = laid_out.split("\n\n")
    return "\n\n".join(parts[1:-1])


class _Business:
    name = ""


_NO_BUSINESS: Any = _Business()


def build_cases(
    runs: Sequence[dict[str, Any]], golden_items: dict[str, dict[str, Any]]
) -> list[Case]:
    """One case per distinct model-written reply in the saved pipeline runs."""
    cases: list[Case] = []
    seen_keys: set[tuple[str, str]] = set()
    for run in runs:
        for item in run["items"]:
            draft = item.get("draft")
            if not draft or draft.get("kind") != "reply" or item["id"] not in golden_items:
                continue
            key = (item["id"], draft["body"])
            if key in seen_keys:
                continue
            seen_keys.add(key)
            passages: list[Source] = []
            for retrieval in item.get("retrievals") or []:
                if not retrieval.get("declined"):
                    _merged(retrieval["sources"], passages)
            gold = golden_items[item["id"]]
            try:
                answer = middle_of(draft["body"])
            except ValueError:
                continue
            cases.append(
                {
                    "id": item["id"],
                    "question": f"{gold.get('subject') or ''}\n{gold['body']}".strip(),
                    "answer": answer,
                    "passages": [p.text for p in passages],
                }
            )
    return cases


# --- judging ---


def judge_case(judge: JudgeLike, case: Case) -> dict[str, Any]:
    result = judge.verdict(
        "faithfulness",
        question=case["question"],
        answer=case["answer"],
        history=(),
        passages=case["passages"],
    )
    return {
        "id": case["id"],
        "verdict": result.get("verdict"),
        "unsupported_claims": result.get("unsupported_claims"),
        "error": result.get("error"),
    }


def judge_all(
    judge: JudgeLike, cases: Sequence[Case], progress: Callable[[int, int], None] | None = None
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for number, case in enumerate(cases, 1):
        results.append(judge_case(judge, case))
        if progress is not None:
            progress(number, len(cases))
    return results


def summarise(results: Sequence[dict[str, Any]]) -> dict[str, Any]:
    scored = [r for r in results if r["verdict"] in VERDICTS]
    counts = Counter(r["verdict"] for r in scored)
    return {
        "drafts": len(results),
        "judged": len(scored),
        "errors": len(results) - len(scored),
        "counts": {v: counts.get(v, 0) for v in VERDICTS},
        "mean": sum(SCORE[r["verdict"]] for r in scored) / len(scored) if scored else None,
        "flagged_ids": [r["id"] for r in scored if r["verdict"] != "supported"],
    }


def render_summary(summary: dict[str, Any], judge_config: dict[str, Any] | None) -> str:
    mean = "n/a" if summary["mean"] is None else f"{summary['mean']:.2f}"
    c = summary["counts"]
    lines = [
        "# Faithfulness of Citedesk drafts, judged by citeCheck's judge",
        "",
        "> SYNTHETIC DATA. Ids and counts only. Not calibrated against hand labels unless a "
        "calibration is reported with it (D-079).",
        "",
        f"- drafts judged: {summary['judged']} of {summary['drafts']} ({summary['errors']} errors)",
        f"- supported {c['supported']}, partly supported {c['partly_supported']}, "
        f"unsupported {c['unsupported']}; mean {mean} (supported 1, partly 0.5, unsupported 0)",
        f"- flagged (not fully supported): {', '.join(summary['flagged_ids']) or 'none'}",
    ]
    if judge_config:
        lines.append(
            f"- judge: {judge_config.get('model')}, prompt v{judge_config.get('prompt_version')}, "
            f"thinking {'on' if judge_config.get('think') else 'off'}"
        )
    return "\n".join(lines) + "\n"


# --- known-bad: does the judge notice damage? ---


def load_plants(path: Path = PLANTS_FILE) -> dict[str, list[str]]:
    """Planted sentences by kind. The one tied to a fixed set of passages is left out: here the
    passages differ from draft to draft."""
    by_kind: dict[str, list[str]] = {}
    for item in json.loads(path.read_text("utf-8"))["items"]:
        if item["kind"] != "wrong_service_price":
            by_kind.setdefault(item["kind"], []).append(item["sentence"])
    return by_kind


def change_price(answer: str) -> str | None:
    """The first dollar amount made $50 larger, so it is in no passage."""
    import re

    match = re.search(r"\$(\d[\d,]*)", answer)
    if not match:
        return None
    value = int(match.group(1).replace(",", "")) + 50
    return answer[: match.start()] + f"${value:,}" + answer[match.end() :]


def add_sentence(answer: str, sentence: str) -> str:
    paragraphs = answer.split("\n\n")
    paragraphs.insert(max(1, len(paragraphs) - 1), sentence)
    return "\n\n".join(paragraphs)


def damaged_cases(
    good: Sequence[Case], plants: dict[str, list[str]], per_kind: int, seed: int = 0
) -> list[dict[str, Any]]:
    """Each kind of damage applied to `per_kind` different good drafts, with rotating sentences."""
    rng = random.Random(seed)  # noqa: S311 (a sample, not a secret)
    cases: list[dict[str, Any]] = []
    for kind in [*sorted(plants), "price_changed"]:
        pool = list(good)
        rng.shuffle(pool)
        made = 0
        for case in pool:
            if kind == "price_changed":
                changed = change_price(case["answer"])
            else:
                sentences = plants[kind]
                changed = add_sentence(case["answer"], sentences[made % len(sentences)])
            if changed is None or changed == case["answer"]:
                continue
            cases.append({**case, "answer": changed, "damage": kind})
            made += 1
            if made >= per_kind:
                break
    return cases


def known_bad_summary(
    controls: Sequence[dict[str, Any]], damaged: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    def flagged(results: Sequence[dict[str, Any]]) -> tuple[int, int]:
        scored = [r for r in results if r["verdict"] in VERDICTS]
        return sum(r["verdict"] != "supported" for r in scored), len(scored)

    kinds: dict[str, tuple[int, int]] = {}
    for kind in sorted({d["damage"] for d in damaged}):
        kinds[kind] = flagged([d for d in damaged if d["damage"] == kind])
    return {"control": flagged(controls), "kinds": kinds}


def render_known_bad(summary: dict[str, Any]) -> str:
    c = summary["control"]
    lines = [
        "# Does the judge notice damage? (D-079)",
        "",
        "> SYNTHETIC DATA. The controls are drafts the judge called supported and the review aids "
        "did not mark, but no person has labelled them: they are a proxy for good drafts.",
        "",
        f"- control (unchanged good drafts) flagged: {c[0]} of {c[1]}",
    ]
    for kind, (flagged, total) in summary["kinds"].items():
        lines.append(f"- {kind}: flagged {flagged} of {total}")
    return "\n".join(lines) + "\n"


# --- hand labels ---


def sample_for_sheet(
    results: Sequence[dict[str, Any]], n: int, seed: int = 0, share_flagged: float = 0.5
) -> list[int]:
    """Indices into `results`: about half the drafts the judge flagged and half it did not,
    shuffled, so the labeller sees no pattern and no verdict."""
    rng = random.Random(seed)  # noqa: S311 (a sample, not a secret)
    flagged = [
        i for i, r in enumerate(results) if r["verdict"] in ("partly_supported", "unsupported")
    ]
    fine = [i for i, r in enumerate(results) if r["verdict"] == "supported"]
    rng.shuffle(flagged)
    rng.shuffle(fine)
    take = min(len(flagged), round(n * share_flagged))
    chosen = flagged[:take] + fine[: n - take]
    rng.shuffle(chosen)
    return chosen


def sheet_markdown(
    cases: Sequence[Case], results: Sequence[dict[str, Any]], order: Sequence[int]
) -> str:
    """A labelling sheet. It shows the message, the passages and the draft, never the judge's
    verdict or the review aids' marks."""
    lines = [
        "# Label these drafts",
        "",
        "SYNTHETIC DATA. For each draft decide only this: is every claim it states backed by the "
        "passages shown? Do not judge whether it is helpful or well written.",
        "",
        "- `supported`: no claim lacks a passage that states it (a claim that follows directly "
        "from passages, such as arithmetic on their figures, counts as backed).",
        "- `partly_supported`: the main claims are backed but a minor one is not.",
        "- `unsupported`: the main claims are not backed.",
        "",
        "A sentence that only manages the conversation (a greeting, a request for details, "
        '"a member of our team will follow up", "please do not send card numbers") states no '
        "fact about the business and is not a claim: leave it out of your decision.",
        "",
        "Write the labels into `eval/labels/draft_faithfulness.labels.json` as "
        '`{"labeller": "...", "labels": {"<id>": "supported", ...}}`.',
        "",
    ]
    for number, index in enumerate(order, 1):
        case = cases[index]
        passages = "\n\n".join(
            f"[{n}] {text.strip()}" for n, text in enumerate(case["passages"], 1)
        )
        lines += [
            f"## {number}. `{case['id']}`",
            "",
            "**Customer message**",
            "",
            case["question"],
            "",
            "**Passages the draft was written from**",
            "",
            passages or "(none)",
            "",
            "**Draft**",
            "",
            case["answer"],
            "",
            "Label: ______",
            "",
        ]
    return "\n".join(lines)


def unique_ids(ids: Sequence[str]) -> list[str]:
    """The same inquiry can have two drafts (from two runs). The first keeps its id; later ones
    get `~2`, `~3`, so each draft has its own label and verdict."""
    seen: Counter[str] = Counter()
    out: list[str] = []
    for item_id in ids:
        seen[item_id] += 1
        out.append(item_id if seen[item_id] == 1 else f"{item_id}~{seen[item_id]}")
    return out


def apply_unique_ids(cases: list[Case], results: list[dict[str, Any]]) -> None:
    """Rename in place, by position: a case and its verdict are the same position in both lists."""
    for case, result, new in zip(cases, results, unique_ids([c["id"] for c in cases]), strict=True):
        case["id"] = result["id"] = new


def merge_template(existing: dict[str, Any], ids: Sequence[str]) -> dict[str, Any]:
    """Add the ids a labels file lacks without touching any label already written."""
    labels = dict(existing.get("labels", {}))
    for item_id in ids:
        labels.setdefault(item_id, "")
    return {"labeller": existing.get("labeller", ""), "labels": labels}


def label_template(ids: Sequence[str]) -> dict[str, Any]:
    """An empty labels file in the sheet's order, for the labeller to fill in."""
    return {"labeller": "", "labels": dict.fromkeys(ids, "")}


def cohens_kappa(pairs: Sequence[tuple[str, str]]) -> float | None:
    if not pairs:
        return None
    n = len(pairs)
    observed = sum(a == b for a, b in pairs) / n
    labels = {x for pair in pairs for x in pair}
    expected = sum(
        (sum(a == k for a, _ in pairs) / n) * (sum(b == k for _, b in pairs) / n) for k in labels
    )
    return None if expected == 1 else (observed - expected) / (1 - expected)


def agreement(labels: dict[str, str], results: Sequence[dict[str, Any]]) -> dict[str, Any]:
    by_id = {r["id"]: r for r in results if r["verdict"] in VERDICTS}
    pairs = [
        (labels[i], by_id[i]["verdict"]) for i in labels if i in by_id and labels[i] in VERDICTS
    ]
    matrix = Counter(pairs)
    flag = lambda v: v != "supported"  # noqa: E731
    return {
        "n": len(pairs),
        "exact": sum(a == b for a, b in pairs),
        "same_side": sum(flag(a) == flag(b) for a, b in pairs),
        "kappa": cohens_kappa(pairs),
        "matrix": {f"{a} -> {b}": n for (a, b), n in sorted(matrix.items())},
        "judge_flags_what_hand_calls_supported": sum(
            1 for a, b in pairs if a == "supported" and b != "supported"
        ),
        "judge_passes_what_hand_flags": sum(
            1 for a, b in pairs if a != "supported" and b == "supported"
        ),
    }


# --- the command line ---


def load_citecheck(src: Path) -> tuple[Any, Any]:
    """The judge and its client from citeCheck's source folder."""
    if not (src / "citecheck").is_dir():
        raise SystemExit(f"citeCheck's source was not found at {src} (use --citecheck PATH)")
    sys.path.insert(0, str(src))
    from citecheck.judge.client import OllamaClient  # type: ignore[import-not-found]
    from citecheck.judge.core import Judge  # type: ignore[import-not-found]

    return Judge, OllamaClient


def make_judge(src: Path) -> Any:
    from citedesk.config import Settings

    host = Settings().ollama_url.split("//")[-1].split(":")[0]
    if host not in LOOPBACK:
        raise SystemExit("the judge model must be on this machine (loopback address)")
    judge_class, client_class = load_citecheck(src)
    return judge_class(client_class(url=Settings().ollama_url))


def _golden_by_id() -> dict[str, dict[str, Any]]:
    data = json.loads(GOLDEN_FILE.read_text("utf-8"))
    return {i["id"]: i for i in data["items"] if i["split"] == "tuned"}


def _say(message: str) -> None:
    print(message, file=sys.stderr)


def _stamp() -> str:
    return f"{datetime.now(UTC):%Y%m%d-%H%M%S}"


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def _progress(label: str) -> Callable[[int, int], None]:
    def show(number: int, total: int) -> None:
        if number == total or number % 10 == 0:
            _say(f"{label}: {number}/{total}")

    return show


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument("command", choices=("judge", "known-bad", "sheet", "calibrate"))
    parser.add_argument("--runs", nargs="*", help="saved pipeline runs (default: all tuned ones)")
    parser.add_argument("--judged", type=Path, help="a file written by `judge`")
    parser.add_argument("--citecheck", type=Path, default=None)
    parser.add_argument("--per-kind", type=int, default=15)
    parser.add_argument("--n", type=int, default=36, help="drafts on the labelling sheet")
    parser.add_argument(
        "--labels", type=Path, default=LABELS_DIR / "draft_faithfulness.labels.json"
    )
    parser.add_argument("--md", type=Path)
    args = parser.parse_args(argv)
    src = args.citecheck or Path(__import__("os").environ.get("CITECHECK_SRC", DEFAULT_CITECHECK))

    if args.command == "judge":
        paths = args.runs or sorted(glob.glob(str(RUNS_DIR / "pipeline-v1-tuned-*.drafts.json")))
        runs = [json.loads(Path(p).read_text("utf-8")) for p in paths]
        cases = build_cases(runs, _golden_by_id())
        if not cases:
            _say("no model-written drafts found in the saved runs")
            return 1
        judge = make_judge(src)
        results = judge_all(judge, cases, _progress("judging"))
        out = RUNS_DIR / f"judge-faithfulness-{_stamp()}.json"
        _write(out, {"config": judge.config(), "cases": cases, "results": results})
        text = render_summary(summarise(results), judge.config())
        if args.md:
            args.md.write_text(text, encoding="utf-8")
        print(text + f"Wrote {out}")
        return 0

    if not args.judged:
        _say("--judged FILE is needed (the file `judge` wrote)")
        return 2
    saved = json.loads(args.judged.read_text("utf-8"))
    cases, results = saved["cases"], saved["results"]
    apply_unique_ids(cases, results)

    if args.command == "known-bad":
        from citedesk import support

        by_id = {r["id"]: r for r in results}
        good = []
        for case in cases:
            if by_id[case["id"]]["verdict"] != "supported":
                continue
            body = f"Hi,\n\n{case['answer']}\n\nKind regards,\nX"
            sources = [Source(file="", section="", page=None, text=t) for t in case["passages"]]
            marked = support.analyse(body, sources, case["question"])
            if all(s.status != "unsupported" for s in marked.sentences) and not any(
                f.mismatch for f in marked.figures
            ):
                good.append(case)
        damaged = damaged_cases(good, load_plants(), args.per_kind)
        judge = make_judge(src)
        verdicts = judge_all(judge, damaged, _progress("known-bad"))
        rows = [{**v, "damage": d["damage"]} for v, d in zip(verdicts, damaged, strict=True)]
        controls = [{"id": c["id"], "verdict": "supported"} for c in good]
        summary = known_bad_summary(controls, rows)
        out = RUNS_DIR / f"judge-known-bad-{_stamp()}.json"
        _write(
            out, {"config": judge.config(), "summary": summary, "cases": damaged, "results": rows}
        )
        text = render_known_bad(summary)
        if args.md:
            args.md.write_text(text, encoding="utf-8")
        print(text + f"Wrote {out}")
        return 0

    if args.command == "sheet":
        order = sample_for_sheet(results, args.n)
        out = RUNS_DIR / "draft-labelling-sheet.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(sheet_markdown(cases, results, order), encoding="utf-8")
        _write(RUNS_DIR / "draft-labelling-sheet.order.json", [cases[i]["id"] for i in order])
        ids = [cases[i]["id"] for i in order]
        current = json.loads(args.labels.read_text("utf-8")) if args.labels.exists() else {}
        _write(args.labels, merge_template(current, ids))
        print(f"Updated {args.labels}: {len(ids)} ids, labels already written are kept")
        print(f"Wrote {out}: {len(order)} drafts, with no verdicts shown")
        return 0

    labels_file = json.loads(args.labels.read_text("utf-8"))
    result = agreement(labels_file["labels"], results)
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
