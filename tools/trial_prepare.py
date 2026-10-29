"""Prepare the reviewer trial (docs/REVIEW_TRIAL.md): 24 inquiries with drafts to review.

    python -m tools.trial_prepare --db data/trial.db --seed 20261030

Needs Ollama and rag-project running and indexed (about 15 minutes). It reads tuned items only, runs
them through the real pipeline, plants one problem in each of six drafts (keeping a plant only if
the real checks still pass it), leaves the rest as the pipeline wrote them, and puts all 24 in
the queue in a shuffled order. What is planted is written to eval/trial/plants.json. Do not open
that file, or tools/trial_plants.py, until the sitting is over.
"""

import argparse
import json
import random
import sqlite3
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from citedesk import pipeline, repo, retrieval
from citedesk.business import Business, load_business
from citedesk.config import Settings
from citedesk.db import connect, migrate
from citedesk.intake import NewInquiry, submit
from citedesk.knowledge import KnowledgeBase, RagProjectKB
from citedesk.models import InquiryStatus, Urgency
from citedesk.providers import LLMProvider
from citedesk.providers.ollama import OllamaProvider
from tools import eval_common as common
from tools import trial_plants as plants

PLAN_FILE = Path("eval/trial/plants.json")
FORMAT = "review-trial-plan-v1"
FIRST_RECEIVED = datetime(2026, 10, 30, 9, 0, tzinfo=UTC)
S = InquiryStatus


class PreparationError(Exception):
    """The trial could not be prepared as the protocol describes."""


def candidates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tuned items that an owner would see on an ordinary day and the system should draft for."""
    return [
        item
        for item in items
        if item["labels"]["urgency"] == "normal"
        and item["labels"]["expected_route"] in ("draft_reply", "request_details")
        and not item["labels"]["should_escalate"]
    ]


def _store(conn: sqlite3.Connection, settings: Settings, item: dict[str, Any]) -> int:
    fields = ("channel", "sender_name", "sender_email", "subject", "body")
    inquiry = NewInquiry.model_validate({k: item[k] for k in fields if item.get(k) is not None})
    return submit(conn, inquiry, settings).id


def _draft_to_the_check(
    conn: sqlite3.Connection,
    inquiry_id: int,
    settings: Settings,
    llm: LLMProvider,
    kb: KnowledgeBase,
    business: Business,
) -> InquiryStatus:
    """Run the real stages up to a stored draft, and stop before the check stage."""
    status = pipeline.process(conn, inquiry_id, settings, llm=llm)
    if status is S.routed:
        status = pipeline.retrieve_stage(conn, inquiry_id, settings, kb, business)
    if status is S.routed:
        status = pipeline.draft_stage(conn, inquiry_id, settings, llm, business)
    return status


def _context(conn: sqlite3.Connection, inquiry_id: int) -> plants.Context:
    inquiry = repo.get_inquiry(conn, inquiry_id)
    draft = repo.latest_draft(conn, inquiry_id)
    if inquiry is None or draft is None:
        raise PreparationError("an inquiry lost its draft")
    sources = retrieval.merged_sources(repo.list_retrievals(conn, inquiry_id))
    return plants.Context(
        body=draft.body,
        customer_name=inquiry.sender_name or "",
        message=f"{inquiry.subject or ''} {inquiry.body}",
        sources_text="\n".join(source.text for source in sources),
    )


def try_plant(
    conn: sqlite3.Connection,
    inquiry_id: int,
    settings: Settings,
    business: Business,
    plant: plants.Plant,
) -> bool:
    """Put the plant in the draft and run the real check stage. Keep it only if the draft is still
    ready for a person (no blocking check failed); otherwise undo everything."""
    draft = repo.latest_draft(conn, inquiry_id)
    if draft is None:
        return False
    conn.execute("BEGIN")
    try:
        conn.execute("UPDATE drafts SET body = ? WHERE id = ?", (plant.body, draft.id))
        status = pipeline.check_stage(conn, inquiry_id, settings, business)
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    if status is S.needs_review:
        conn.execute("COMMIT")
        return True
    conn.execute("ROLLBACK")
    return False


def prepare(
    conn: sqlite3.Connection,
    settings: Settings,
    llm: LLMProvider,
    kb: KnowledgeBase,
    business: Business,
    items: list[dict[str, Any]],
    *,
    seed: int,
    warmup: int = 4,
    ordinary: int = 14,
    progress: Callable[[str], None] = lambda line: None,
) -> dict[str, Any]:
    """Build the trial inside `conn` and return the plan. Everything not used is deleted."""
    rng = random.Random(seed)  # noqa: S311 (a seeded shuffle, not a secret)
    pool = candidates(items)
    rng.shuffle(pool)

    drafted: dict[int, dict[str, Any]] = {}
    for number, item in enumerate(pool, start=1):
        inquiry_id = _store(conn, settings, item)
        try:
            status = _draft_to_the_check(conn, inquiry_id, settings, llm, kb, business)
        except Exception as error:  # noqa: BLE001 (a candidate that fails is left out)
            progress(f"[{number}/{len(pool)}] {item['id']}: left out ({type(error).__name__})")
            continue
        classification = repo.latest_classification(conn, inquiry_id)
        normal = classification is not None and classification.urgency is Urgency.normal
        if status is S.drafted and normal:
            drafted[inquiry_id] = item
        progress(f"[{number}/{len(pool)}] {item['id']}: {status.value}")

    planted: dict[int, tuple[str, plants.Plant]] = {}
    for kind in plants.KINDS:
        for inquiry_id in list(drafted):
            if inquiry_id in planted:
                continue
            plant = plants.make(kind, _context(conn, inquiry_id))
            if plant is not None and try_plant(conn, inquiry_id, settings, business, plant):
                planted[inquiry_id] = (kind, plant)
                break
        else:
            raise PreparationError(f"no draft could take a planted problem of kind {kind!r}")

    ready: list[int] = []
    for inquiry_id in drafted:
        if inquiry_id in planted:
            continue
        if pipeline.check_stage(conn, inquiry_id, settings, business) is S.needs_review:
            ready.append(inquiry_id)
    rng.shuffle(ready)
    if len(ready) < warmup + 1:
        raise PreparationError(f"only {len(ready)} ordinary drafts were ready; need more items")
    ordinary = min(ordinary, len(ready) - warmup)
    warm, rest = ready[:warmup], ready[warmup : warmup + ordinary]

    keep = {*warm, *rest, *planted}
    for row in conn.execute("SELECT id FROM inquiries").fetchall():
        if int(row["id"]) not in keep:
            conn.execute("DELETE FROM inquiries WHERE id = ?", (int(row["id"]),))

    scored = [*rest, *planted]
    rng.shuffle(scored)
    sitting = [(i, "warmup") for i in warm] + [
        (i, "planted" if i in planted else "ordinary") for i in scored
    ]
    order: list[dict[str, Any]] = []
    for position, (inquiry_id, role) in enumerate(sitting, start=1):
        received = (FIRST_RECEIVED + timedelta(minutes=position)).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute("UPDATE inquiries SET received_at = ? WHERE id = ?", (received, inquiry_id))
        kind, plant = planted.get(inquiry_id, (None, None))
        order.append(
            {
                "position": position,
                "inquiry_id": inquiry_id,
                "item_id": drafted[inquiry_id]["id"],
                "role": role,
                "kind": kind,
                "marker": plant.marker if plant else None,
            }
        )
    return {
        "format": FORMAT,
        "seed": seed,
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model": getattr(llm, "model", None),
        "counts": {
            "warmup": len(warm),
            "ordinary": len(rest),
            "planted": len(planted),
            "left_out": len(pool) - len(drafted),
        },
        "order": order,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--db", type=Path, default=Path("data/trial.db"))
    parser.add_argument("--seed", type=int, default=20261030)
    parser.add_argument("--plan", type=Path, default=PLAN_FILE)
    args = parser.parse_args(argv)
    if args.db.exists() or args.plan.exists():
        print(f"Refused: {args.db} or {args.plan} already exists; remove them to start again.")
        return 2
    settings = Settings()
    args.db.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(args.db)
    migrate(conn)
    golden = json.loads(common.GOLDEN_FILE.read_text("utf-8"))
    items = common.select_split(golden, "tuned")  # never the held-out items
    llm = OllamaProvider.from_settings(settings)
    kb = RagProjectKB(settings.rag_url)
    business = load_business(settings.business_facts_path)
    try:
        plan = prepare(conn, settings, llm, kb, business, items, seed=args.seed, progress=print)
    except PreparationError as error:
        conn.close()
        args.db.unlink(missing_ok=True)
        print(f"Could not prepare the trial: {error}", file=sys.stderr)
        return 1
    conn.close()
    common.write_json_atomic(args.plan, plan)
    counts = plan["counts"]
    print(
        f"Prepared {args.db}: {counts['warmup']} warm-up, {counts['ordinary']} ordinary and "
        f"{counts['planted']} planted drafts. The plan is in {args.plan}: do not open it yet."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
