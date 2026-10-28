"""Score stages 1 to 3 (screen, understand, route) on the tuned golden split.

Run (needs Ollama with the model; see CLAUDE.md):
    python -m tools.score_understanding             run the tuned split with the real model
    python -m tools.score_understanding --limit 10  only the first 10 items (a check, not a result)
    python -m tools.score_understanding --from RUN  score a saved run again; no model is called

A run sends every message through the real pipeline code into a throwaway in-memory database, with
`received_at` pinned to the golden file's reference date so relative dates do not drift. It writes
`eval/runs/<id>.run.json` (what the pipeline produced, with provenance) and `<id>.scores.json`
(the metrics). They hold the model's outputs, which paraphrase the synthetic messages, and never
the messages themselves. Runs are git-ignored.

What is measured, and the rules for it, are in `score_run` and the report's footnotes. This is the
Phase 4 scorer; Phase 7 builds the full runner. The held-out split is not run here: it is run once,
in Phase 7, and never used to tune.
"""

import argparse
import hashlib
import json
import re
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from citedesk import events, pipeline, repo, understand
from citedesk.business import Business
from citedesk.config import Settings
from citedesk.db import connect, migrate
from citedesk.intake import NewInquiry, submit
from citedesk.knowledge import KnowledgeBase
from citedesk.models import AuditEventType, ReasonCode, Stage
from citedesk.providers import LLMProvider
from tools.golden import GOLDEN_FILE, REPO_ROOT

RUNS_DIR = REPO_ROOT / "eval/runs"
FIELDS = ("service_type", "start_date", "property_type", "address_area", "booking_reference")
SCORED_REASONS = (
    ReasonCode.HEALTH_SAFETY,
    ReasonCode.COMPLAINT,
    ReasonCode.REFUND_OR_DISPUTE,
    ReasonCode.LEGAL_THREAT,
    ReasonCode.POLICY_EXCEPTION_REQUEST,
    ReasonCode.INJECTION_SUSPECTED,
    ReasonCode.LOW_CONFIDENCE,
)
NOT_IN_KB = ReasonCode.NOT_IN_KNOWLEDGE_BASE.value
SCREEN_ONLY_REASONS = {ReasonCode.INJECTION_SUSPECTED.value, ReasonCode.HEALTH_SAFETY.value}


# --- what the pipeline should have done, from the labels --------------------------------------


def expected_outcome(labels: dict[str, Any]) -> tuple[str, list[str]]:
    """The route and reasons the labels imply for stages 1 to 3.

    Two labelled things cannot happen yet. `NOT_IN_KNOWLEDGE_BASE` comes from the knowledge base
    (Phase 5), so an item labelled only with it is expected on the draft path here. And a message
    that screening escalates for injection is never read by the model (TRD 4.1), so only the
    screening reasons can be expected of it.
    """
    reasons = [code for code in labels["expected_reason_codes"] if code != NOT_IN_KB]
    if ReasonCode.INJECTION_SUSPECTED.value in reasons:
        reasons = [code for code in reasons if code in SCREEN_ONLY_REASONS]
    route = labels["expected_route"]
    if labels["expected_reason_codes"] == [NOT_IN_KB]:
        route = "draft_reply"
    return route, reasons


# --- running -----------------------------------------------------------------------------------


def golden_sha256(path: Path = GOLDEN_FILE) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_state() -> dict[str, Any]:
    def git(*args: str) -> str | None:
        try:
            done = subprocess.run(  # noqa: S603 (fixed arguments)
                ["git", *args],  # noqa: S607
                capture_output=True,
                text=True,
                check=True,
                cwd=REPO_ROOT,
            )
        except (OSError, subprocess.CalledProcessError):
            return None
        return done.stdout.strip()

    return {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain"))}


def collect(
    conn: Any, inquiry_id: int, item_id: str, *, with_drafts: bool = False
) -> dict[str, Any]:
    """What the pipeline left behind for one inquiry: codes and model output, no message text.

    With `with_drafts` it also keeps what was retrieved and the draft with its checks. Those are
    text the system wrote about a customer message, so only the Phase 5 reading run asks for them.
    """
    inquiry = repo.get_inquiry(conn, inquiry_id)
    if inquiry is None:
        raise LookupError(f"no inquiry {inquiry_id}")
    classification = repo.latest_classification(conn, inquiry_id)
    extraction = repo.latest_extraction(conn, inquiry_id)
    attempts = None
    for event in events.list_events(conn, inquiry_id):
        if event.event_type is AuditEventType.stage_finished and event.stage is Stage.understand:
            attempts = event.payload.get("attempts")
    record: dict[str, Any] = {
        "id": item_id,
        "status": inquiry.status.value,
        "route": inquiry.route.value if inquiry.route else None,
        "urgency": inquiry.urgency.value if inquiry.urgency else None,
        "primary_intent": inquiry.primary_intent.value if inquiry.primary_intent else None,
        "classified": classification is not None,
        "reasons": [
            {"code": e.reason_code.value, "source": e.source.value}
            for e in repo.list_escalations(conn, inquiry_id)
        ],
        "failure_stage": inquiry.failure_stage.value if inquiry.failure_stage else None,
        "failure_message": inquiry.failure_message,
    }
    if classification is not None and extraction is not None:
        model_said = json.loads(classification.raw_response)
        record |= {
            "intents": [
                {"intent": i.intent.value, "confidence": i.confidence.value}
                for i in classification.intents
            ],
            "primary_confidence": classification.primary_confidence.value,
            "sentiment": classification.sentiment.value,
            "model_urgency": model_said["urgency"],
            "model_signals": model_said["escalation_signals"],
            "safety_net_hit": classification.safety_net_hit,
            "fields": extraction.fields.model_dump(mode="json"),
            "missing_fields": extraction.missing_fields,
            "model_ms": classification.duration_ms,
            "attempts": attempts,
            "raw_response": classification.raw_response,
        }
    if with_drafts:
        draft = repo.latest_draft(conn, inquiry_id)
        record["retrievals"] = [
            {
                "question": r.question,
                "declined": r.declined,
                "answer": r.kb_answer,
                "sources": [s.model_dump() for s in r.sources],
            }
            for r in repo.list_retrievals(conn, inquiry_id)
        ]
        record["draft"] = None
        record["checks"] = []
        if draft is not None:
            record["draft"] = {
                "kind": draft.kind.value,
                "status": draft.status.value,
                "model": draft.model,
                "subject": draft.subject,
                "body": draft.body,
                "claims": [c.model_dump() for c in draft.claims],
            }
            record["checks"] = [
                {
                    "code": c.check_code.value,
                    "blocking": c.blocking,
                    "passed": c.passed,
                    "detail": c.detail,
                }
                for c in repo.list_draft_checks(conn, draft.id)
            ]
    return record


def run_items(
    items: list[dict[str, Any]],
    settings: Settings,
    llm: LLMProvider,
    *,
    reference_date: str,
    progress: Callable[[int, int, dict[str, Any]], None] | None = None,
    kb: KnowledgeBase | None = None,
    business: Business | None = None,
    with_drafts: bool = False,
) -> list[dict[str, Any]]:
    """Send each item through the pipeline into a throwaway database and collect the outcomes."""
    conn = connect(":memory:")
    migrate(conn)
    stamp = f"{reference_date}T12:00:00Z"
    results: list[dict[str, Any]] = []
    for number, item in enumerate(items, start=1):
        inquiry = NewInquiry.model_validate(
            {
                "external_id": item["id"],
                "channel": item["channel"],
                "sender_name": item["sender_name"],
                "sender_email": item.get("sender_email"),
                "subject": item.get("subject"),
                "body": item["body"],
                "received_at": stamp,
            }
        )
        inquiry_id = submit(conn, inquiry, settings, now=stamp).id
        pipeline.process(conn, inquiry_id, settings, llm=llm, kb=kb, business=business)
        record = collect(conn, inquiry_id, item["id"], with_drafts=with_drafts)
        results.append(record)
        if progress is not None:
            progress(number, len(items), record)
    return results


# --- scoring -----------------------------------------------------------------------------------


def ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def normalise_value(value: Any) -> str | None:
    """Compare fields as a person would: ignore case, punctuation and the word "unknown"."""
    if value is None:
        return None
    text = value.value if isinstance(value, Enum) else str(value)
    text = " ".join(re.sub(r"[^\w\s-]", "", text.lower()).split())
    return None if text in ("", "unknown") else text


def same_area(predicted: str | None, label: str | None) -> bool:
    """Lenient match for the free-text area: one contains the other."""
    if predicted is None or label is None:
        return predicted == label
    return predicted in label or label in predicted


def prf(true_positive: int, false_positive: int, false_negative: int) -> dict[str, Any]:
    return {
        "tp": true_positive,
        "fp": false_positive,
        "fn": false_negative,
        "precision": ratio(true_positive, true_positive + false_positive),
        "recall": ratio(true_positive, true_positive + false_negative),
    }


def intent_scores(rows: list[tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
    """Primary-intent accuracy and macro-F1 over the items the model read."""
    correct = sum(
        1 for result, item in rows if result["primary_intent"] == item["labels"]["primary_intent"]
    )
    set_match = sum(
        1
        for result, item in rows
        if {i["intent"] for i in result["intents"]} == set(item["labels"]["intents"])
    )
    primary_in_labels = sum(
        1 for result, item in rows if result["primary_intent"] in item["labels"]["intents"]
    )
    support: Counter[str] = Counter(item["labels"]["primary_intent"] for _, item in rows)
    predicted: Counter[str] = Counter(result["primary_intent"] for result, _ in rows)
    hits: Counter[str] = Counter(
        item["labels"]["primary_intent"]
        for result, item in rows
        if result["primary_intent"] == item["labels"]["primary_intent"]
    )
    per_intent: dict[str, Any] = {}
    f1s: list[float] = []
    for intent in sorted(set(support) | set(predicted)):
        precision = ratio(hits[intent], predicted[intent])
        recall = ratio(hits[intent], support[intent])
        f1 = 2 * precision * recall / (precision + recall) if precision and recall else 0.0
        per_intent[intent] = {
            "support": support[intent],
            "predicted": predicted[intent],
            "correct": hits[intent],
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
        if support[intent]:
            f1s.append(f1)
    return {
        "n": len(rows),
        "primary_accuracy": ratio(correct, len(rows)),
        "primary_correct": correct,
        "intent_set_exact": ratio(set_match, len(rows)),
        "primary_in_labelled_set": ratio(primary_in_labels, len(rows)),
        "macro_f1": statistics.fmean(f1s) if f1s else None,
        "per_intent": per_intent,
        "wrong": sorted(
            f"{item['id']}: {item['labels']['primary_intent']} -> {result['primary_intent']}"
            for result, item in rows
            if result["primary_intent"] != item["labels"]["primary_intent"]
        ),
    }


def field_scores(rows: list[tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
    """Exact match per field after normalising, over the items the model read."""
    per_field: dict[str, Any] = {}
    total_correct = total_cells = items_all_correct = 0
    for name in FIELDS:
        correct = present = present_correct = spurious = lenient = 0
        for result, item in rows:
            label = normalise_value(item["labels"]["fields"].get(name))
            got = normalise_value(result["fields"].get(name))
            correct += got == label
            lenient += (got == label) if name != "address_area" else same_area(got, label)
            if label is not None:
                present += 1
                present_correct += got == label
            elif got is not None:
                spurious += 1
        per_field[name] = {
            "accuracy": ratio(correct, len(rows)),
            "label_present": present,
            "recall_when_present": ratio(present_correct, present),
            "spurious_when_absent": spurious,
            "lenient_accuracy": ratio(lenient, len(rows)),
        }
        total_correct += correct
        total_cells += len(rows)
    for result, item in rows:
        if all(
            normalise_value(result["fields"].get(n))
            == normalise_value(item["labels"]["fields"].get(n))
            for n in FIELDS
        ):
            items_all_correct += 1
    return {
        "n": len(rows),
        "accuracy": ratio(total_correct, total_cells),
        "items_with_every_field_right": ratio(items_all_correct, len(rows)),
        "per_field": per_field,
    }


def escalation_scores(
    results: dict[str, dict[str, Any]], items: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Escalation precision and recall over every item (screening escalations included)."""
    tp = fp = fn = tn = 0
    false_positives: list[str] = []
    false_negatives: list[str] = []
    for item_id, item in items.items():
        wanted = expected_outcome(item["labels"])[0] == "escalate"
        got = results[item_id]["route"] == "escalate"
        if wanted and got:
            tp += 1
        elif got:
            fp += 1
            false_positives.append(item_id)
        elif wanted:
            fn += 1
            false_negatives.append(item_id)
        else:
            tn += 1
    per_reason: dict[str, Any] = {}
    for code in SCORED_REASONS:
        r_tp = r_fp = r_fn = 0
        misses: list[str] = []
        extras: list[str] = []
        for item_id, item in items.items():
            wanted = code.value in expected_outcome(item["labels"])[1]
            got = any(r["code"] == code.value for r in results[item_id]["reasons"])
            if wanted and got:
                r_tp += 1
            elif got:
                r_fp += 1
                extras.append(item_id)
            elif wanted:
                r_fn += 1
                misses.append(item_id)
        per_reason[code.value] = prf(r_tp, r_fp, r_fn) | {"missed": misses, "extra": extras}
    return {
        "n": len(items),
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        **prf(tp, fp, fn),
        "false_positives": sorted(false_positives),
        "false_negatives": sorted(false_negatives),
        "per_reason": per_reason,
    }


def route_scores(
    results: dict[str, dict[str, Any]], items: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    matrix: dict[str, Counter[str]] = defaultdict(Counter)
    correct = 0
    for item_id, item in items.items():
        wanted = expected_outcome(item["labels"])[0]
        got = results[item_id]["route"] or "none"
        matrix[wanted][got] += 1
        correct += got == wanted
    return {
        "accuracy": ratio(correct, len(items)),
        "matrix": {wanted: dict(counts) for wanted, counts in sorted(matrix.items())},
    }


def safety_scores(
    results: dict[str, dict[str, Any]], items: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Who caught each safety item: the model, the keyword net, both, or neither."""
    who: Counter[str] = Counter()
    for item_id, item in items.items():
        if ReasonCode.HEALTH_SAFETY.value not in item["labels"]["expected_reason_codes"]:
            continue
        result = results[item_id]
        if not result["classified"]:
            who["escalated_before_the_model" if result["route"] == "escalate" else "neither"] += 1
            continue
        by_model = any(i["intent"] == "health_or_safety" for i in result["intents"])
        by_net = result["safety_net_hit"]
        who[
            "both"
            if by_model and by_net
            else "model_only"
            if by_model
            else "net_only"
            if by_net
            else "neither"
        ] += 1
    fired = sum(1 for r in results.values() if r.get("safety_net_hit"))
    return {"safety_items_by_who_caught_them": dict(who), "items_the_net_fired_on": fired}


def urgency_scores(rows: list[tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
    correct = sum(1 for result, item in rows if result["urgency"] == item["labels"]["urgency"])
    model_correct = sum(
        1 for result, item in rows if result["model_urgency"] == item["labels"]["urgency"]
    )
    return {
        "n": len(rows),
        "accuracy": ratio(correct, len(rows)),
        "model_alone_accuracy": ratio(model_correct, len(rows)),
        "wrong": sorted(
            f"{item['id']}: {item['labels']['urgency']} -> {result['urgency']}"
            for result, item in rows
            if result["urgency"] != item["labels"]["urgency"]
        ),
    }


def score_run(run: dict[str, Any], golden_items: list[dict[str, Any]]) -> dict[str, Any]:
    """All the metrics for a run. Pure: the same run and labels always give the same numbers."""
    items = {item["id"]: item for item in golden_items}
    results = {record["id"]: record for record in run["items"]}
    items = {item_id: items[item_id] for item_id in results}  # score what was run, in run order
    read = [(results[i], items[i]) for i in items if results[i]["classified"]]
    not_read = Counter(
        "failed" if results[i]["status"] == "failed" else f"{results[i]['status']}_at_screening"
        for i in items
        if not results[i]["classified"]
    )
    times = sorted(r["model_ms"] for r, _ in read if r.get("model_ms") is not None)
    return {
        "items": len(items),
        "read_by_the_model": len(read),
        "not_read_by_the_model": dict(not_read),
        "failures": sorted(
            f"{i}: {results[i]['failure_stage']} - {results[i]['failure_message']}"
            for i in items
            if results[i]["status"] == "failed"
        ),
        "intent": intent_scores(read),
        "fields": field_scores(read),
        "urgency": urgency_scores(read),
        "escalation": escalation_scores(results, items),
        "route": route_scores(results, items),
        "safety_net": safety_scores(results, items),
        "retried": sum(1 for r, _ in read if (r.get("attempts") or 1) > 1),
        "latency_ms": {
            "median": statistics.median(times) if times else None,
            "p90": times[int(0.9 * (len(times) - 1))] if times else None,
            "max": times[-1] if times else None,
        },
    }


# --- report ------------------------------------------------------------------------------------


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{100 * value:.1f}%"


def report(run: dict[str, Any], scores: dict[str, Any]) -> str:
    header = run["header"]
    intent, fields, esc, route = (
        scores["intent"],
        scores["fields"],
        scores["escalation"],
        scores["route"],
    )
    c = esc["confusion"]
    dirty = " (uncommitted changes)" if header["git"]["dirty"] else ""
    thinking = "on" if header["settings"]["enable_thinking"] else "off"
    lines = [
        f"Run {header['run_id']}: {scores['items']} items, split {header['split']}, "
        f"model {header['model']}, prompt {header['prompt_version']}",
        f"commit {header['git']['commit']}{dirty}, golden {header['golden_sha256'][:12]}, "
        f"thinking {thinking}",
        "",
        "Coverage",
        f"  read by the model         {scores['read_by_the_model']}",
        f"  not read (screening)      {scores['not_read_by_the_model']}",
        f"  failed                    {len(scores['failures'])}",
        f"  needed a second attempt   {scores['retried']}",
        "",
        f"Intent (over the {intent['n']} items the model read)",
        f"  primary intent accuracy   {pct(intent['primary_accuracy'])}  "
        f"({intent['primary_correct']}/{intent['n']})",
        f"  macro-F1                  {pct(intent['macro_f1'])}",
        f"  intent set matches        {pct(intent['intent_set_exact'])}",
        f"  primary is a labelled one {pct(intent['primary_in_labelled_set'])}",
        "",
        f"Fields (over the {fields['n']} items the model read; match ignores case and punctuation)",
        f"  overall                   {pct(fields['accuracy'])}",
        f"  items with every field right {pct(fields['items_with_every_field_right'])}",
    ]
    for name, f in fields["per_field"].items():
        lines.append(
            f"  {name:<18} {pct(f['accuracy']):>7}   "
            f"right when given {pct(f['recall_when_present']):>7}"
            f" (of {f['label_present']})   invented when absent {f['spurious_when_absent']}"
            + (f"   lenient {pct(f['lenient_accuracy'])}" if name == "address_area" else "")
        )
    lines += [
        "",
        f"Urgency (over the items the model read)    {pct(scores['urgency']['accuracy'])}"
        f"   model alone {pct(scores['urgency']['model_alone_accuracy'])}",
        "",
        f"Escalation (over all {esc['n']} items; as far as stages 1 to 3 can know)",
        f"  precision                 {pct(esc['precision'])}  (tp {c['tp']}, fp {c['fp']})",
        f"  recall                    {pct(esc['recall'])}  (tp {c['tp']}, fn {c['fn']})",
        f"  false positives           {', '.join(esc['false_positives']) or 'none'}",
        f"  false negatives           {', '.join(esc['false_negatives']) or 'none'}",
        "  by reason (small counts; each row is a rough guide)",
    ]
    for code, r in esc["per_reason"].items():
        lines.append(
            f"    {code:<26} tp {r['tp']:>2}  fp {r['fp']:>2}  fn {r['fn']:>2}"
            f"   precision {pct(r['precision']):>7}  recall {pct(r['recall']):>7}"
        )
    lines += [
        "",
        f"Route accuracy              {pct(route['accuracy'])}",
        "  expected -> got: " + "; ".join(f"{w}: {d}" for w, d in route["matrix"].items()),
        "",
        f"Emergency net: fired on {scores['safety_net']['items_the_net_fired_on']} items; "
        f"safety items caught by {scores['safety_net']['safety_items_by_who_caught_them']}",
        f"Model time per item: median {scores['latency_ms']['median']} ms, "
        f"p90 {scores['latency_ms']['p90']} ms, max {scores['latency_ms']['max']} ms",
        "",
        "What this cannot tell you",
        "  - These are the tuned items: the net and the labelling rules were written with them",
        "    in view. The held-out set is the honest test and is run once, in Phase 7.",
        "  - The labeller and the prompt share an author, and one hand wrote every label.",
        "  - Counts per reason are small (8 safety items, 2 legal threats): a recall of 100%",
        "    on 8 is compatible with a true miss rate near one in three.",
        "  - NOT_IN_KNOWLEDGE_BASE needs the knowledge base (Phase 5); an item labelled with only",
        "    that is expected on the draft path here. A message screening escalates for injection",
        "    is never read by the model, so its other labelled reasons are not expected.",
        "  - Drafts and their checks are not scored here.",
    ]
    if intent["wrong"]:
        lines += ["", "Intent mistakes (label -> model)"] + [f"  {w}" for w in intent["wrong"]]
    if scores["failures"]:
        lines += ["", "Failures"] + [f"  {f}" for f in scores["failures"]]
    return "\n".join(lines)


# --- command line ------------------------------------------------------------------------------


def load_golden() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(GOLDEN_FILE.read_text("utf-8"))
    return data


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )


def make_run(
    items: list[dict[str, Any]],
    settings: Settings,
    llm: LLMProvider,
    *,
    split: str,
    reference_date: str,
    progress: Callable[[int, int, dict[str, Any]], None] | None = None,
    kb: KnowledgeBase | None = None,
    business: Business | None = None,
    with_drafts: bool = False,
) -> dict[str, Any]:
    started = datetime.now(UTC)
    results = run_items(
        items,
        settings,
        llm,
        reference_date=reference_date,
        progress=progress,
        kb=kb,
        business=business,
        with_drafts=with_drafts,
    )
    finished = datetime.now(UTC)
    return {
        "header": {
            "run_id": f"{understand.PROMPT_VERSION}-{split}-{started:%Y%m%d-%H%M%S}",
            "split": split,
            "stages": ["screen", "understand", "route"],
            "model": llm.model,
            "prompt_version": understand.PROMPT_VERSION,
            "settings": {
                "enable_thinking": settings.enable_thinking,
                "escalate_on_low_confidence": settings.escalate_on_low_confidence,
                "spam_threshold": settings.spam_threshold,
            },
            "golden_sha256": golden_sha256(),
            "reference_date": reference_date,
            "git": git_state(),
            "started_at": started.isoformat(timespec="seconds"),
            "finished_at": finished.isoformat(timespec="seconds"),
            "python": sys.version.split()[0],
        },
        "items": results,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument("--split", default="tuned", help="only 'tuned' can be scored here")
    parser.add_argument("--limit", type=int, help="run only the first N items (not a result)")
    parser.add_argument("--from", dest="source", type=Path, help="score a saved run file again")
    args = parser.parse_args(argv)
    if args.split != "tuned":
        print(
            "The held-out split is run once, in Phase 7, and never used to tune. "
            "This script scores the tuned split only.",
            file=sys.stderr,
        )
        return 2

    golden = load_golden()
    if args.source is not None:
        run = json.loads(args.source.read_text("utf-8"))
        out_base = args.source.with_suffix("")
    else:
        from citedesk.providers.ollama import OllamaProvider

        items = [i for i in golden["items"] if i["split"] == args.split]
        if args.limit:
            items = items[: args.limit]
        settings = Settings()
        llm = OllamaProvider.from_settings(settings)
        began = time.monotonic()

        def progress(number: int, total: int, record: dict[str, Any]) -> None:
            seconds = (record.get("model_ms") or 0) / 1000
            print(
                f"[{number}/{total}] {record['id']}: {record['status']} "
                f"({seconds:.1f}s model, {time.monotonic() - began:.0f}s elapsed)",
                file=sys.stderr,
            )

        run = make_run(
            items,
            settings,
            llm,
            split=args.split,
            reference_date=golden["header"]["reference_date"],
            progress=progress,
        )
        out_base = RUNS_DIR / run["header"]["run_id"]
        write_json(Path(f"{out_base}.run.json"), run)

    scores = score_run(run, golden["items"])
    write_json(Path(f"{str(out_base).removesuffix('.run')}.scores.json"), scores)
    print(report(run, scores))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
