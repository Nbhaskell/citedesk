"""Run the whole pipeline (screen to check) on a golden split and save what it produced.

    python -m tools.eval_run                                  tuned split, one pass
    python -m tools.eval_run --passes 3 --label think-off     three passes, three files
    python -m tools.eval_run --thinking on --label think-on   the model reads with thinking on
    python -m tools.eval_run --limit 8                        a quick check, not a result
    python -m tools.eval_run --resume RUN_ID                  carry on an interrupted run
    python -m tools.eval_run --split heldout --allow-heldout --heldout-passes 3   see below
    python -m tools.eval_run --split sealed --confirm-sealed-once --sealed-passes 3   see below
    python -m tools.eval_run --set fernhollow --split heldout --allow-heldout --heldout-passes 3

Needs Ollama with the model and rag-project indexed on Citedesk's documents (README). This asks
the system and saves raw outputs; it does not score them. `python -m tools.eval_score` does that
from the saved file, with no model.

**Saved runs** go to `eval/runs/<id>.run.json` (git-ignored: they hold synthetic messages and the
system's drafts). The file is rewritten after every item, so an interrupted run leaves a partial
file that `--resume` continues. The pipeline runs against a SQLite file next to it
(`<id>.db`), not memory, because later items depend on earlier ones (a sender seen before is
"known" to screening); resuming reopens it. The database is deleted when the run completes unless
`--keep-db` is given. The header records the commit, the code tree, whether the tree was dirty,
settings, model, prompt versions, sampling, rag-project's configuration, and hashes of the golden
file and of the split that was run.

**Held-out split.** It is run once, by one fixed system (D-061, D-062). It needs `--allow-heldout`,
a clean tree, the whole split (no `--limit`), and on the first run `--heldout-passes N` (1 to 5):
the passes are declared before the first item is read. Every held-out run is written into the
committed ledger `eval/heldout_ledger.json` before its first item. A pass beyond those declared, a
fresh start of an unfinished run, or a run of a different system is refused unless `--justify TEXT`
gives a reason, which the ledger keeps. Tuned runs never touch the ledger.

**Sealed set** (D-071). The same rules, with its own committed ledger `eval/sealed_ledger.json`
and two more: the run needs `--confirm-sealed-once`, and the sealed file
(`data/sealed/citedesk_sealed_v1.json`, git-ignored) must match the hash committed in
`eval/golden/citedesk_sealed.sha256`, or nothing is read. The first run declares its passes with
`--sealed-passes N`. Its labels come from the sealed file, not `citedesk_v1.json`.

**The electrician's set** (`--set fernhollow`, D-099, D-100). The invented electrician's labelled
set is held-out only and follows the held-out rules above, with its own committed ledger
`eval/fernhollow_ledger.json`. The run uses the electrician's fact sheet
(`universe-electrical/facts.json`) whatever `BUSINESS_FACTS_PATH` says, and before anything is
written it asks the knowledge base for the business's contact details and refuses unless the
passages that come back are the electrician's: rag-project must be indexed on
`universe-electrical/docs`.
"""

import argparse
import json
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from citedesk import drafting, pipeline, repo, understand
from citedesk.business import Business, load_business
from citedesk.config import Settings
from citedesk.db import connect, migrate
from citedesk.health import check_knowledge_base, check_model
from citedesk.intake import NewInquiry, submit
from citedesk.knowledge import KnowledgeBase, RagProjectKB
from citedesk.providers import LLMProvider
from tools import eval_common as ec
from tools import eval_ledger as ledger_mod
from tools import score_understanding as su
from tools.golden import SETS

FORMAT = "eval-run-v1"
STAGES = ["screen", "understand", "route", "retrieve", "draft", "check"]
Progress = Callable[[int, int, dict[str, Any]], None]


class RunRefused(Exception):
    """The run cannot start or resume. The message says why."""


# --- the header ----------------------------------------------------------------------------------


def settings_record(settings: Settings) -> dict[str, Any]:
    return {
        "enable_thinking": settings.enable_thinking,
        "escalate_on_low_confidence": settings.escalate_on_low_confidence,
        "spam_threshold": settings.spam_threshold,
        "duplicate_window_hours": settings.duplicate_window_hours,
        "draft_max_words": settings.draft_max_words,
        "max_body_chars": settings.max_body_chars,
    }


def build_header(
    *,
    split: str,
    split_items: list[dict[str, Any]],
    run_items: list[dict[str, Any]],
    settings: Settings,
    model: str,
    golden_header: dict[str, Any],
    golden_sha256: str,
    git: dict[str, Any],
    rag: dict[str, Any],
    run_id: str,
    reference_date: str,
    limit: int | None = None,
    label: str | None = None,
    pass_number: int = 1,
    passes_planned: int = 1,
) -> dict[str, Any]:
    """Provenance for a run. `split_sha256` is the hash of the whole split, whether or not a
    `limit` cut the run short, so passes and settings of one split can be told apart from a
    different split without depending on the other splits in the file."""
    return {
        "format": FORMAT,
        "run_id": run_id,
        "label": label,
        "split": split,
        "limit": limit,
        "stages": STAGES,
        "model": model,
        "prompt_versions": {
            "understand": understand.PROMPT_VERSION,
            "draft": drafting.PROMPT_VERSION,
        },
        "settings": settings_record(settings),
        "sampling": {
            "understand": {
                "temperature": 0.0,
                "seed": understand.SEED,
                "max_tokens": understand.MAX_TOKENS,
                "thinking_first_attempt": settings.enable_thinking,
            },
            "draft": {
                "temperature": drafting.TEMPERATURE,
                "seed": drafting.SEED,
                "max_tokens": drafting.MAX_TOKENS,
                "thinking": False,
            },
        },
        "rag": rag,
        "golden": {key: golden_header.get(key) for key in ("name", "version", "docs_sha256")},
        "golden_sha256": golden_sha256,
        "split_sha256": ec.split_sha256(split_items),
        "items_planned": len(run_items),
        "reference_date": reference_date,
        "git": git,
        "python": sys.version.split()[0],
        "pass_number": pass_number,
        "passes_planned": passes_planned,
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "finished_at": None,
        "complete": False,
    }


def system_identity(header: dict[str, Any]) -> dict[str, Any]:
    """What makes two runs the same system. No times, no commit id (committing the ledger moves
    the commit but not the code), no counts that change as a run goes on."""
    git = header["git"]
    return {
        "code_tree": git.get("code_tree"),
        "universe_tree": git.get("universe_tree"),
        "model": header["model"],
        "prompt_versions": header["prompt_versions"],
        "settings": header["settings"],
        "rag": ec.rag_identity(header.get("rag") or {}),
        "split_sha256": header["split_sha256"],
    }


# --- running -------------------------------------------------------------------------------------


def _inquiry_for(conn: Any, item: dict[str, Any], settings: Settings, stamp: str) -> int:
    existing = repo.find_by_external_id(conn, item["channel"], item["id"])
    if existing is not None:
        return existing.id  # a resumed run that stopped part-way through this item
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
    return submit(conn, inquiry, settings, now=stamp).id


def execute_run(
    *,
    items: list[dict[str, Any]],
    settings: Settings,
    llm: LLMProvider,
    kb: KnowledgeBase,
    business: Business,
    header: dict[str, Any],
    out_path: Path,
    db_path: Path,
    progress: Progress | None = None,
    resume: bool = False,
    keep_db: bool = False,
) -> dict[str, Any]:
    """Send each item through the pipeline and save the run after every one."""
    if resume:
        if not out_path.exists():
            raise RunRefused(f"there is no run file to resume at {out_path.name}")
        run = json.loads(out_path.read_text("utf-8"))
        saved = run["header"]
        if saved.get("complete"):
            raise RunRefused(f"{out_path.name} is complete: there is nothing to resume")
        if system_identity(saved) != system_identity(header) or saved.get("limit") != header.get(
            "limit"
        ):
            raise RunRefused(
                "this is not the system that started this run (code, model, settings, prompts, "
                "knowledge base or split differ): resuming would mix two systems in one run"
            )
        if not db_path.exists() and run["items"]:
            raise RunRefused(
                "the run's database is missing, so the earlier items' effect on later ones "
                "(known senders) cannot be rebuilt: start a new run"
            )
        run["header"].setdefault("resumed_at", []).append(
            datetime.now(UTC).isoformat(timespec="seconds")
        )
    else:
        if out_path.exists():
            raise RunRefused(f"{out_path.name} already exists: a run never overwrites a file")
        run = {"header": header, "items": []}
    done = {record["id"] for record in run["items"]}
    stamp = f"{header['reference_date']}T12:00:00Z"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    try:
        migrate(conn)
        ec.write_json_atomic(out_path, run)
        for number, item in enumerate(items, start=1):
            if item["id"] in done:
                continue
            inquiry_id = _inquiry_for(conn, item, settings, stamp)
            pipeline.process(conn, inquiry_id, settings, llm=llm, kb=kb, business=business)
            record = su.collect(conn, inquiry_id, item["id"], with_drafts=True)
            run["items"].append(record)
            ec.write_json_atomic(out_path, run)
            if progress is not None:
                progress(number, len(items), record)
    finally:
        conn.close()
    run["header"]["complete"] = True
    run["header"]["finished_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    ec.write_json_atomic(out_path, run)
    if not keep_db:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{db_path}{suffix}").unlink(missing_ok=True)
    return run


# --- the command ---------------------------------------------------------------------------------


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument("--split", choices=ec.SPLITS, default="tuned")
    parser.add_argument(
        "--set", choices=ec.GOLDEN_SETS, default="kestrel", help="the labelled set (D-100)"
    )
    parser.add_argument(
        "--limit", type=int, help="run only the first N items (a check, not a result)"
    )
    parser.add_argument("--passes", type=int, default=1, help="passes to make, one file each")
    parser.add_argument(
        "--label", help="a short name for the setting being run (goes in file names)"
    )
    parser.add_argument(
        "--thinking", choices=("on", "off"), help="override ENABLE_THINKING for the model's reading"
    )
    parser.add_argument("--resume", metavar="RUN_ID", help="continue an unfinished run")
    parser.add_argument("--keep-db", action="store_true", help="keep the run's database file")
    parser.add_argument("--allow-heldout", action="store_true", help="permit --split heldout")
    parser.add_argument(
        "--heldout-passes", type=int, help="passes declared by the first held-out run"
    )
    parser.add_argument(
        "--confirm-sealed-once",
        action="store_true",
        help="permit --split sealed (D-071): one evaluation of one fixed system",
    )
    parser.add_argument("--sealed-passes", type=int, help="passes declared by the first sealed run")
    parser.add_argument(
        "--justify", help="a written reason for anything beyond the declared passes"
    )
    args = parser.parse_args(argv)
    if args.passes < 1:
        parser.error("--passes must be at least 1")
    return args


def _say(message: str) -> None:
    print(message, file=sys.stderr)


def _run_id(
    split: str,
    label: str | None,
    pass_number: int,
    stamp: datetime,
    golden_set: str = "kestrel",
) -> str:
    parts = [
        "eval",
        *([golden_set] if golden_set != "kestrel" else []),
        split,
        *([label] if label else []),
        f"{stamp:%Y%m%d-%H%M%S}",
        f"p{pass_number}",
    ]
    return "-".join(parts)


def run_command(
    args: argparse.Namespace,
    *,
    golden: dict[str, Any],
    golden_sha256: str,
    settings: Settings,
    llm: LLMProvider,
    kb: KnowledgeBase,
    business: Business,
    git: dict[str, Any],
    rag: dict[str, Any],
    runs_dir: Path,
    ledger_path: Path,
    preflight: Callable[[], str | None],
    progress: Progress | None = None,
    sealed_ledger_path: Path | None = None,
    sealed_hash_matches: Callable[[], bool] = lambda: False,
) -> int:
    """Everything `main` does once its inputs exist, so a test can supply scripted ones."""
    split: str = args.split
    golden_set: str = args.set
    resumed: dict[str, Any] | None = None
    if args.resume:
        path = Path(args.resume)
        path = path if path.suffix else runs_dir / f"{args.resume}.run.json"
        if not path.exists():
            _say(f"no run file {path.name}")
            return 2
        resumed = json.loads(path.read_text("utf-8"))["header"]
        split = resumed["split"]
        golden_set = str(resumed.get("golden_set") or "kestrel")
    problems = set_problems(golden_set, split)
    problems += ledger_mod.heldout_problems(
        allow_heldout=args.allow_heldout,
        limit=args.limit if resumed is None else resumed.get("limit"),
        dirty=bool(git.get("dirty")),
        git_known=git.get("commit") is not None and git.get("dirty") is not None,
        split=split,
    )
    problems += ledger_mod.sealed_problems(
        split=split,
        confirmed=args.confirm_sealed_once,
        limit=args.limit if resumed is None else resumed.get("limit"),
        dirty=bool(git.get("dirty")),
        git_known=git.get("commit") is not None and git.get("dirty") is not None,
        hash_matches=sealed_hash_matches() if split == "sealed" else True,
    )
    if split == "sealed" and sealed_ledger_path is None:
        problems.append("no sealed ledger is configured")
    if problems:
        for problem in problems:
            _say(f"Refused: {problem}")
        return 2
    problem = preflight()
    if problem:
        _say(f"Refused: {problem}")
        return 2

    if args.thinking:
        settings = settings.model_copy(update={"enable_thinking": args.thinking == "on"})
    split_items = ec.select_split(golden, split)
    limit = resumed.get("limit") if resumed else args.limit
    run_items = split_items[:limit] if limit else split_items
    if not run_items:
        _say(f"the {split} split has no items")
        return 2
    reference_date = golden["header"].get("reference_date", "2026-10-28")
    locked_path = sealed_ledger_path if split == "sealed" else ledger_path
    ledger = ledger_mod.load(locked_path, split) if split in ec.LOCKED_SPLITS else None
    declared_passes = args.sealed_passes if split == "sealed" else args.heldout_passes
    began = time.monotonic()

    def say_progress(number: int, total: int, record: dict[str, Any]) -> None:
        seconds = sum(record.get("stage_ms", {}).values()) / 1000
        _say(
            f"[{number}/{total}] {record['id']}: {record['status']} "
            f"({seconds:.1f}s, {time.monotonic() - began:.0f}s elapsed)"
        )
        if progress is not None:
            progress(number, total, record)

    pass_range = [resumed["pass_number"]] if resumed else range(1, args.passes + 1)
    for pass_number in pass_range:
        now = datetime.now(UTC)
        justification = None
        run_id = (
            resumed["run_id"]
            if resumed
            else _run_id(split, args.label, pass_number, now, golden_set)
        )
        label = resumed.get("label") if resumed else args.label
        header = build_header(
            split=split,
            split_items=split_items,
            run_items=run_items,
            settings=settings,
            model=llm.model,
            golden_header=golden["header"],
            golden_sha256=golden_sha256,
            git=git,
            rag=rag,
            run_id=run_id,
            reference_date=reference_date,
            limit=limit,
            label=label,
            pass_number=pass_number,
            passes_planned=args.passes,
        )
        if golden_set != "kestrel":
            # Not part of the system identity: the split hash already tells the sets apart.
            header["golden_set"] = golden_set
            header["business"] = {"name": business.name, "trade": business.trade.key}
        if ledger is not None:
            try:
                auth = ledger_mod.authorize(
                    ledger,
                    system_identity(header),
                    passes=declared_passes,
                    justify=args.justify,
                    resume_run_id=run_id if resumed else None,
                )
            except ledger_mod.LedgerRefused as refusal:
                _say(f"Refused: {refusal}")
                return 2
            pass_number = auth.pass_number
            if not resumed:
                run_id = _run_id(split, args.label, pass_number, now, golden_set)
                header["run_id"], header["pass_number"] = run_id, pass_number
            justification = auth.justification
            ledger_mod.record_start(
                ledger,
                auth,
                system_identity(header),
                run_id=run_id,
                run_file=f"{run_id}.run.json",
                now=now.isoformat(timespec="seconds"),
            )
            ledger_mod.save(locked_path, ledger)
        if justification:
            header["justification_in_ledger"] = True
        out_path = runs_dir / f"{run_id}.run.json"
        _say(f"Run {run_id}: {len(run_items)} items from the {split} split")
        try:
            run = execute_run(
                items=run_items,
                settings=settings,
                llm=llm,
                kb=kb,
                business=business,
                header=header,
                out_path=out_path,
                db_path=runs_dir / f"{run_id}.db",
                progress=say_progress,
                resume=resumed is not None,
                keep_db=args.keep_db,
            )
        except RunRefused as refusal:
            _say(f"Refused: {refusal}")
            return 2
        if ledger is not None:
            ledger_mod.record_finish(
                ledger,
                run_id,
                now=datetime.now(UTC).isoformat(timespec="seconds"),
                items=len(run["items"]),
                failed=sum(1 for r in run["items"] if r["status"] == "failed"),
            )
            ledger_mod.save(locked_path, ledger)
        failed = sum(1 for r in run["items"] if r["status"] == "failed")
        print(f"Wrote {out_path} ({len(run['items'])} items, {failed} failed)")
        if header.get("limit"):
            print("This was a quick check (--limit), not a result.")
    return 0


def _preflight(settings: Settings) -> str | None:
    model = check_model(settings)
    if model.status != "ok":
        return f"the model is not available ({model.reason})"
    kb = check_knowledge_base(settings)
    if kb.status != "ok":
        return f"the knowledge base is not ready ({kb.reason}); index it first (README)"
    return None


def set_problems(golden_set: str, split: str) -> list[str]:
    """Reasons a set and split cannot be run together."""
    if golden_set not in SETS:
        return [f"there is no golden set {golden_set!r}"]
    # The plumber's set has its tuned, held-out and sealed splits, each with its own rules.
    if golden_set != "kestrel" and split not in SETS[golden_set].splits:
        return [
            f"the {golden_set} set has held-out items only and is never used for tuning: "
            "use --split heldout"
        ]
    return []


def facts_for_set(golden_set: str) -> Path | None:
    """The fact sheet a set must be run with, or None to keep the settings' own."""
    if golden_set == "kestrel":
        return None
    return SETS[golden_set].docs_dir.parent / "facts.json"


KB_CHECK_QUESTION = "What is the office phone number and email address?"


def kb_serves(kb: KnowledgeBase, business: Business) -> str | None:
    """None if the knowledge base's passages are this business's (its phone or email appears in
    them), otherwise why not. Two invented businesses have documents with the same file names, so
    the names alone cannot tell which one is indexed."""
    try:
        result = kb.ask(KB_CHECK_QUESTION)
    except Exception as error:  # noqa: BLE001 (any failure means the check did not pass)
        return f"the knowledge base could not be asked ({type(error).__name__})"
    text = "\n".join(source.text for source in result.sources)
    if business.phone in text or business.email in text:
        return None
    return (
        f"the knowledge base's passages are not {business.name}'s: index rag-project on that "
        "business's documents first"
    )


def _split_to_run(args: argparse.Namespace) -> str:
    """The split this invocation will run: a resumed run keeps the split it started with."""
    if args.resume:
        path = Path(args.resume)
        path = path if path.suffix else ec.RUNS_DIR / f"{args.resume}.run.json"
        if path.exists():
            return str(json.loads(path.read_text("utf-8"))["header"]["split"])
    return str(args.split)


def _set_to_run(args: argparse.Namespace) -> str:
    """The set this invocation will run: a resumed run keeps the set it started with."""
    if args.resume:
        path = Path(args.resume)
        path = path if path.suffix else ec.RUNS_DIR / f"{args.resume}.run.json"
        if path.exists():
            header = json.loads(path.read_text("utf-8"))["header"]
            return str(header.get("golden_set") or "kestrel")
    return str(args.set)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    early = ledger_mod.heldout_problems(
        allow_heldout=args.allow_heldout,
        limit=args.limit,
        dirty=False,
        git_known=True,
        split=args.split,
    ) + ledger_mod.sealed_problems(
        split=args.split,
        confirmed=args.confirm_sealed_once,
        limit=args.limit,
        dirty=False,
        git_known=True,
        hash_matches=True,
    )
    if early:
        for problem in early:
            _say(f"Refused: {problem}")
        return 2

    from citedesk.providers.ollama import OllamaProvider
    from tools.golden import SEALED_FILE, SEALED_HASH_FILE, verify_sealed

    settings = Settings()
    split = _split_to_run(args)
    golden_set = _set_to_run(args)
    early_set = set_problems(golden_set, split)
    if early_set:
        for problem in early_set:
            _say(f"Refused: {problem}")
        return 2
    facts = facts_for_set(golden_set)
    if facts is not None:
        settings = settings.model_copy(update={"business_facts_path": facts})
    git = ec.git_state()
    if split == "sealed":
        # Refused here, before the file is opened: a request that will be turned down must not
        # read the sealed set at all.
        refused = ledger_mod.sealed_problems(
            split=split,
            confirmed=args.confirm_sealed_once,
            limit=args.limit,
            dirty=bool(git.get("dirty")),
            git_known=git.get("commit") is not None and git.get("dirty") is not None,
            hash_matches=verify_sealed(SEALED_FILE, SEALED_HASH_FILE),
        )
        if refused:
            for problem in refused:
                _say(f"Refused: {problem}")
            return 2
    golden_path = ec.golden_file_for(split, golden_set)
    if not golden_path.is_file():
        _say(f"Refused: {golden_path.name} does not exist")
        return 2
    golden = json.loads(golden_path.read_text("utf-8"))
    business = load_business(settings.business_facts_path)
    kb = RagProjectKB(settings.rag_url)

    def preflight() -> str | None:
        problem = _preflight(settings)
        if problem is None and golden_set != "kestrel":
            problem = kb_serves(kb, business)
        return problem

    return run_command(
        args,
        golden=golden,
        golden_sha256=ec.file_sha256(golden_path),
        settings=settings,
        llm=OllamaProvider.from_settings(settings),
        kb=kb,
        business=business,
        git=git,
        rag=ec.rag_status(settings.rag_url),
        runs_dir=ec.RUNS_DIR,
        ledger_path=ec.ledger_file_for(golden_set),
        preflight=preflight,
        sealed_ledger_path=ec.SEALED_LEDGER_FILE,
        sealed_hash_matches=lambda: verify_sealed(SEALED_FILE, SEALED_HASH_FILE),
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
