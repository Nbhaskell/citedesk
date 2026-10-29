"""The Phase 7 runner, with a scripted model and knowledge base.

No test here reads the held-out items: the "held-out" runs below use tuned items copied under a
different split name, so the ledger and the guards can be exercised without the real split.
"""

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from citedesk.business import Business
from citedesk.config import Settings
from citedesk.knowledge import FakeKB
from citedesk.providers import FakeLLM
from citedesk.screening import screen
from tests.golden_data import tuned_golden
from tests.helpers import perfect_reply
from tools import eval_common as ec
from tools import eval_ledger as ledger_mod
from tools import eval_run as er

BUSINESS = Business("Kestrel Hollow Plumbing", "555-0171", "555-0172", "kestrelhollow@example.com")
DRAFT = {
    "subject": "Re: Question",
    "body": "Hi,\n\nDrain cleaning starts at $149.\n\nKind regards,\nKestrel Hollow Plumbing",
    "claims": [{"text": "starts at $149", "source_index": 0}],
}
ITEMS = tuned_golden()["items"][:14]
GIT = {
    "commit": "c" * 40,
    "dirty": False,
    "dirty_paths": 0,
    "code_tree": "a" * 40,
    "universe_tree": "b" * 40,
}
RAG = {"chat_model": "qwen3:8b", "embed_model": "x", "thinking": True, "chunks": 83, "files": 8}


class Halt(BaseException):  # not an Exception: the pipeline must not swallow it, as with Ctrl-C
    pass


def model_for(items: list[dict[str, Any]], *, halt_on_call: int | None = None) -> FakeLLM:
    by_body = {
        screen(i.get("subject"), i["body"], spam_threshold=0.8).body.strip(): i for i in items
    }
    calls = {"n": 0}

    def reply(call: Any) -> dict[str, Any]:
        calls["n"] += 1
        if halt_on_call is not None and calls["n"] == halt_on_call:
            raise Halt
        if "claims" in call.schema["properties"]:
            return DRAFT
        return perfect_reply(next(i for b, i in by_body.items() if b in call.user))

    return FakeLLM(reply)


def kb() -> FakeKB:
    return FakeKB(lambda q: FakeKB.answered("$149", ["pricing.md"], text="Drain cleaning: $149"))


def header(**over: Any) -> dict[str, Any]:
    return er.build_header(
        split="tuned",
        split_items=ITEMS,
        run_items=ITEMS,
        settings=Settings(_env_file=None),
        model="fake-model",
        golden_header={"name": "citedesk_v1", "version": 1, "docs_sha256": "d" * 64},
        golden_sha256="e" * 64,
        git=GIT,
        rag=RAG,
        run_id="run-1",
        reference_date="2026-10-28",
        **over,
    )


def go(tmp_path: Path, **over: Any) -> dict[str, Any]:
    args: dict[str, Any] = {
        "items": ITEMS,
        "settings": Settings(_env_file=None),
        "llm": model_for(ITEMS),
        "kb": kb(),
        "business": BUSINESS,
        "header": header(),
        "out_path": tmp_path / "run-1.run.json",
        "db_path": tmp_path / "run-1.db",
    }
    return er.execute_run(**(args | over))


@pytest.fixture(scope="module")
def finished(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    return go(tmp_path_factory.mktemp("run"))


# --- what a finished run holds -----------------------------------------------------------------


def test_a_finished_run_has_every_item_and_says_it_is_complete(finished: dict[str, Any]) -> None:
    assert finished["header"]["complete"] is True
    assert [r["id"] for r in finished["items"]] == [i["id"] for i in ITEMS]
    assert finished["header"]["finished_at"]


def test_each_item_keeps_stage_times_route_events_and_the_draft(finished: dict[str, Any]) -> None:
    drafted = [r for r in finished["items"] if r["draft"]]
    assert drafted
    record = drafted[0]
    assert {"understand", "route", "retrieve", "draft", "check"} <= set(record["stage_ms"])
    assert record["route_events"][0]["stage"] == "route"
    assert record["checks"] and record["retrievals"]


def test_the_header_names_the_system_and_the_data(finished: dict[str, Any]) -> None:
    h = finished["header"]
    assert h["format"] == "eval-run-v1"
    assert h["stages"] == ["screen", "understand", "route", "retrieve", "draft", "check"]
    assert h["prompt_versions"] == {"understand": "understand-v1", "draft": "draft-v1"}
    assert h["model"] == "fake-model" and h["settings"]["enable_thinking"] is True
    assert h["git"]["code_tree"] == "a" * 40 and h["rag"]["chunks"] == 83
    assert h["golden_sha256"] == "e" * 64 and h["golden"]["docs_sha256"] == "d" * 64
    assert h["split_sha256"] == ec.split_sha256(ITEMS)
    assert h["items_planned"] == len(ITEMS) and h["limit"] is None
    assert h["sampling"]["draft"]["temperature"] == 0.2 and h["sampling"]["understand"]["seed"] == 0


def test_the_split_hash_covers_the_whole_split_even_when_only_some_items_run() -> None:
    limited = er.build_header(
        split="tuned",
        split_items=ITEMS,
        run_items=ITEMS[:3],
        settings=Settings(_env_file=None),
        model="m",
        golden_header={},
        golden_sha256="e" * 64,
        git=GIT,
        rag=RAG,
        run_id="r",
        reference_date="2026-10-28",
        limit=3,
    )
    assert limited["split_sha256"] == ec.split_sha256(ITEMS)
    assert limited["limit"] == 3 and limited["items_planned"] == 3


def test_the_run_database_is_removed_when_the_run_is_complete(tmp_path: Path) -> None:
    go(tmp_path)
    assert not (tmp_path / "run-1.db").exists()


def test_the_database_can_be_kept_for_a_look(tmp_path: Path) -> None:
    go(tmp_path, keep_db=True)
    assert (tmp_path / "run-1.db").exists()


def test_a_run_never_overwrites_a_file_that_is_there(tmp_path: Path) -> None:
    (tmp_path / "run-1.run.json").write_text("{}", encoding="utf-8")
    with pytest.raises(er.RunRefused, match="already exists"):
        go(tmp_path)


# --- partial files and resuming ----------------------------------------------------------------


def test_the_file_is_written_after_every_item_and_marked_incomplete(tmp_path: Path) -> None:
    seen: list[tuple[int, bool]] = []
    path = tmp_path / "run-1.run.json"

    def watch(number: int, total: int, record: dict[str, Any]) -> None:
        saved = json.loads(path.read_text("utf-8"))
        seen.append((len(saved["items"]), saved["header"]["complete"]))

    go(tmp_path, progress=watch)
    assert [n for n, _ in seen] == list(range(1, len(ITEMS) + 1))
    assert not any(done for _, done in seen)
    assert json.loads(path.read_text("utf-8"))["header"]["complete"] is True


def stable(record: dict[str, Any]) -> dict[str, Any]:
    """The parts of a record that do not depend on the clock."""
    return {k: v for k, v in record.items() if k not in {"stage_ms", "model_ms"}}


def test_an_interrupted_run_resumes_to_the_same_result(tmp_path: Path) -> None:
    (tmp_path / "whole").mkdir()
    whole = go(tmp_path / "whole")

    def stop_after_five(number: int, total: int, record: dict[str, Any]) -> None:
        if number == 5:
            raise Halt

    broken = tmp_path / "broken"
    broken.mkdir()
    with pytest.raises(Halt):
        go(broken, progress=stop_after_five)
    partial = json.loads((broken / "run-1.run.json").read_text("utf-8"))
    assert len(partial["items"]) == 5 and partial["header"]["complete"] is False

    llm = model_for(ITEMS)
    resumed = go(broken, resume=True, llm=llm)
    assert [stable(r) for r in resumed["items"]] == [stable(r) for r in whole["items"]]
    assert resumed["header"]["resumed_at"]
    assert resumed["header"]["complete"] is True
    # the five finished items were not sent to the model again
    understood_again = [c for c in llm.calls if "claims" not in c.schema["properties"]]
    assert len(understood_again) < len(ITEMS)


def test_a_crash_in_the_middle_of_an_item_resumes_at_that_item(tmp_path: Path) -> None:
    whole_dir = tmp_path / "whole"
    whole_dir.mkdir()
    whole = go(whole_dir)
    crash_dir = tmp_path / "crash"
    crash_dir.mkdir()
    with pytest.raises(Halt):
        go(crash_dir, llm=model_for(ITEMS, halt_on_call=7))
    saved = json.loads((crash_dir / "run-1.run.json").read_text("utf-8"))
    assert 0 < len(saved["items"]) < len(ITEMS)
    resumed = go(crash_dir, resume=True)
    assert [stable(r) for r in resumed["items"]] == [stable(r) for r in whole["items"]]


def test_resuming_a_run_that_is_complete_is_refused(tmp_path: Path) -> None:
    go(tmp_path, keep_db=True)
    with pytest.raises(er.RunRefused, match="complete"):
        go(tmp_path, resume=True)


def test_resuming_without_the_database_is_refused(tmp_path: Path) -> None:
    def stop(number: int, total: int, record: dict[str, Any]) -> None:
        if number == 3:
            raise Halt

    with pytest.raises(Halt):
        go(tmp_path, progress=stop)
    (tmp_path / "run-1.db").unlink()
    for leftover in tmp_path.glob("run-1.db-*"):
        leftover.unlink()
    with pytest.raises(er.RunRefused, match="database"):
        go(tmp_path, resume=True)


@pytest.mark.parametrize(
    "change",
    [
        {"settings": Settings(_env_file=None, enable_thinking=False)},
        {"model": "another-model"},
        {"rag": RAG | {"chunks": 99}},
        {"git": GIT | {"code_tree": "f" * 40}},
    ],
)
def test_resuming_with_a_different_system_is_refused(
    tmp_path: Path, change: dict[str, Any]
) -> None:
    def stop(number: int, total: int, record: dict[str, Any]) -> None:
        if number == 3:
            raise Halt

    with pytest.raises(Halt):
        go(tmp_path, progress=stop)
    kwargs = {
        "split": "tuned",
        "split_items": ITEMS,
        "run_items": ITEMS,
        "settings": Settings(_env_file=None),
        "model": "fake-model",
        "golden_header": {"name": "citedesk_v1", "version": 1, "docs_sha256": "d" * 64},
        "golden_sha256": "e" * 64,
        "git": GIT,
        "rag": RAG,
        "run_id": "run-1",
        "reference_date": "2026-10-28",
    } | change
    with pytest.raises(er.RunRefused, match="not the system"):
        go(tmp_path, resume=True, header=er.build_header(**kwargs))


# --- the identity the ledger uses --------------------------------------------------------------


def test_the_system_identity_leaves_out_times_and_commit_ids(finished: dict[str, Any]) -> None:
    identity = er.system_identity(finished["header"])
    text = json.dumps(identity)
    assert finished["header"]["started_at"] not in text and "c" * 40 not in text
    assert identity["code_tree"] == "a" * 40 and identity["split_sha256"]
    assert "last_sync" not in identity["rag"]


def test_a_changed_setting_is_a_different_system() -> None:
    a = er.system_identity(header())
    b = er.system_identity(header() | {"settings": {"enable_thinking": True}})
    assert ledger_mod.system_id(a) != ledger_mod.system_id(b)


# --- the command: guards, passes and the ledger ------------------------------------------------


def heldout_copy() -> dict[str, Any]:
    """Tuned items filed under the held-out name, so no real held-out item is touched."""
    items = copy.deepcopy(ITEMS[:6])
    for item in items:
        item["split"] = "heldout"
    return {"header": {"name": "x", "version": 1, "reference_date": "2026-10-28"}, "items": items}


def command(
    tmp_path: Path,
    argv: list[str],
    golden: dict[str, Any] | None = None,
    progress: Any = None,
) -> int:
    golden = golden or heldout_copy()
    items = golden["items"]
    return er.run_command(
        er.parse_args(argv),
        golden=golden,
        golden_sha256="e" * 64,
        settings=Settings(_env_file=None),
        llm=model_for(items),
        kb=kb(),
        business=BUSINESS,
        git=GIT,
        rag=RAG,
        runs_dir=tmp_path / "runs",
        ledger_path=tmp_path / "ledger.json",
        preflight=lambda: None,
        progress=progress,
    )


def test_a_held_out_run_without_the_flag_is_refused_before_anything_is_written(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert command(tmp_path, ["--split", "heldout"]) == 2
    assert "--allow-heldout" in capsys.readouterr().err
    assert not (tmp_path / "ledger.json").exists() and not (tmp_path / "runs").exists()


def test_a_partial_held_out_run_is_refused(tmp_path: Path) -> None:
    argv = ["--split", "heldout", "--allow-heldout", "--heldout-passes", "1", "--limit", "2"]
    assert command(tmp_path, argv) == 2
    assert not (tmp_path / "ledger.json").exists()


def test_the_first_held_out_run_must_declare_its_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert command(tmp_path, ["--split", "heldout", "--allow-heldout"]) == 2
    assert "--heldout-passes" in capsys.readouterr().err
    assert not (tmp_path / "ledger.json").exists()


def test_a_dirty_tree_stops_a_held_out_run(tmp_path: Path) -> None:
    golden = heldout_copy()
    code = er.run_command(
        er.parse_args(["--split", "heldout", "--allow-heldout", "--heldout-passes", "1"]),
        golden=golden,
        golden_sha256="e" * 64,
        settings=Settings(_env_file=None),
        llm=model_for(golden["items"]),
        kb=kb(),
        business=BUSINESS,
        git=GIT | {"dirty": True},
        rag=RAG,
        runs_dir=tmp_path / "runs",
        ledger_path=tmp_path / "ledger.json",
        preflight=lambda: None,
    )
    assert code == 2 and not (tmp_path / "ledger.json").exists()


def test_a_failed_preflight_stops_a_held_out_run_before_the_ledger(tmp_path: Path) -> None:
    golden = heldout_copy()

    def down() -> str:
        return "the knowledge base is not reachable"

    code = er.run_command(
        er.parse_args(["--split", "heldout", "--allow-heldout", "--heldout-passes", "1"]),
        golden=golden,
        golden_sha256="e" * 64,
        settings=Settings(_env_file=None),
        llm=model_for(golden["items"]),
        kb=kb(),
        business=BUSINESS,
        git=GIT,
        rag=RAG,
        runs_dir=tmp_path / "runs",
        ledger_path=tmp_path / "ledger.json",
        preflight=down,
    )
    assert code == 2 and not (tmp_path / "ledger.json").exists()


def test_a_held_out_run_is_written_into_the_ledger_before_its_first_item(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    golden = heldout_copy()
    seen: list[str] = []
    original = er.execute_run

    def spy(*args: Any, **kwargs: Any) -> dict[str, Any]:
        saved = json.loads((tmp_path / "ledger.json").read_text("utf-8"))
        seen.append(saved["evaluations"][0]["runs"][0]["status"])
        return original(*args, **kwargs)

    monkeypatch.setattr(er, "execute_run", spy)
    argv = ["--split", "heldout", "--allow-heldout", "--heldout-passes", "1"]
    assert command(tmp_path, argv, golden) == 0
    assert seen == ["started"]
    final = json.loads((tmp_path / "ledger.json").read_text("utf-8"))
    run = final["evaluations"][0]["runs"][0]
    assert run["status"] == "completed" and run["items"] == len(golden["items"])


def test_an_interrupted_held_out_run_is_resumed_and_uses_no_second_pass(tmp_path: Path) -> None:
    golden = heldout_copy()

    def stop(number: int, total: int, record: dict[str, Any]) -> None:
        if number == 2:
            raise Halt

    argv = ["--split", "heldout", "--allow-heldout", "--heldout-passes", "1"]
    with pytest.raises(Halt):
        command(tmp_path, argv, golden, progress=stop)
    ledger = json.loads((tmp_path / "ledger.json").read_text("utf-8"))
    [run] = ledger["evaluations"][0]["runs"]
    assert run["status"] == "started"
    # a fresh start is a second look: refused
    assert command(tmp_path, ["--split", "heldout", "--allow-heldout"], golden) == 2
    # resuming is not
    resume = ["--split", "heldout", "--allow-heldout", "--resume", run["run_id"]]
    assert command(tmp_path, resume, golden) == 0
    ledger = json.loads((tmp_path / "ledger.json").read_text("utf-8"))
    [run] = ledger["evaluations"][0]["runs"]
    assert run["status"] == "completed" and run["resumed_at"]
    saved = json.loads((tmp_path / "runs" / run["run_file"]).read_text("utf-8"))
    assert len(saved["items"]) == len(golden["items"])


def test_a_second_held_out_run_of_the_same_system_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    golden = heldout_copy()
    first = ["--split", "heldout", "--allow-heldout", "--heldout-passes", "1"]
    assert command(tmp_path, first, golden) == 0
    capsys.readouterr()
    assert command(tmp_path, ["--split", "heldout", "--allow-heldout"], golden) == 2
    assert "(1 of 1)" in capsys.readouterr().err
    assert len(list((tmp_path / "runs").glob("*.run.json"))) == 1


def test_the_declared_passes_run_one_after_another_and_stop(tmp_path: Path) -> None:
    golden = heldout_copy()
    argv = ["--split", "heldout", "--allow-heldout", "--heldout-passes", "2", "--passes", "2"]
    assert command(tmp_path, argv, golden) == 0
    runs = json.loads((tmp_path / "ledger.json").read_text("utf-8"))["evaluations"][0]["runs"]
    assert [r["pass"] for r in runs] == [1, 2]
    assert command(tmp_path, ["--split", "heldout", "--allow-heldout"], golden) == 2


def test_an_extra_pass_with_a_written_reason_is_allowed_and_recorded(tmp_path: Path) -> None:
    golden = heldout_copy()
    first = ["--split", "heldout", "--allow-heldout", "--heldout-passes", "1"]
    assert command(tmp_path, first, golden) == 0
    reason = "the first pass lost items to a model timeout, re-run for the report"
    again = ["--split", "heldout", "--allow-heldout", "--justify", reason]
    assert command(tmp_path, again, golden) == 0
    runs = json.loads((tmp_path / "ledger.json").read_text("utf-8"))["evaluations"][0]["runs"]
    assert runs[1]["outside_plan"] is True and runs[1]["justification"] == reason


def test_a_tuned_run_does_not_touch_the_ledger(tmp_path: Path) -> None:
    golden = {"header": {}, "items": copy.deepcopy(ITEMS[:5])}
    assert command(tmp_path, ["--split", "tuned"], golden) == 0
    assert not (tmp_path / "ledger.json").exists()
    assert len(list((tmp_path / "runs").glob("*.run.json"))) == 1


def test_several_tuned_passes_make_one_file_each(tmp_path: Path) -> None:
    golden = {"header": {}, "items": copy.deepcopy(ITEMS[:4])}
    assert (
        command(tmp_path, ["--split", "tuned", "--passes", "3", "--label", "think-off"], golden)
        == 0
    )
    files = sorted((tmp_path / "runs").glob("*.run.json"))
    assert len(files) == 3
    passes = [json.loads(f.read_text("utf-8"))["header"]["pass_number"] for f in files]
    assert sorted(passes) == [1, 2, 3]
    assert all("think-off" in f.name for f in files)


def test_a_limited_tuned_run_is_marked(tmp_path: Path) -> None:
    golden = {"header": {}, "items": copy.deepcopy(ITEMS[:6])}
    assert command(tmp_path, ["--split", "tuned", "--limit", "2"], golden) == 0
    [file] = (tmp_path / "runs").glob("*.run.json")
    saved = json.loads(file.read_text("utf-8"))
    assert saved["header"]["limit"] == 2 and len(saved["items"]) == 2


def test_thinking_can_be_set_for_a_comparison(tmp_path: Path) -> None:
    golden = {"header": {}, "items": copy.deepcopy(ITEMS[:2])}
    assert command(tmp_path, ["--split", "tuned", "--thinking", "on"], golden) == 0
    [file] = (tmp_path / "runs").glob("*.run.json")
    assert json.loads(file.read_text("utf-8"))["header"]["settings"]["enable_thinking"] is True


def test_the_command_line_only_accepts_the_two_splits() -> None:
    with pytest.raises(SystemExit):
        er.parse_args(["--split", "all"])


def test_main_refuses_a_held_out_request_before_reading_any_file(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert er.main(["--split", "heldout"]) == 2
    assert "--allow-heldout" in capsys.readouterr().err
