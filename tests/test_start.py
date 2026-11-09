"""The one-command start (tools/start.py, D-102): the plain decisions it makes. Nothing here
starts a process or opens a connection."""

from pathlib import Path

import pytest

from tools import start


def make_rag(folder: Path, windows: bool = True) -> Path:
    (folder / "chat.py").parent.mkdir(parents=True, exist_ok=True)
    (folder / "chat.py").write_text("", encoding="utf-8")
    python = folder / ("venv/Scripts/python.exe" if windows else "venv/bin/python")
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")
    return folder


def test_each_business_has_its_own_documents_and_index() -> None:
    kestrel, fernhollow = start.BUSINESSES["kestrel"], start.BUSINESSES["fernhollow"]
    assert kestrel.facts == start.REPO_ROOT / "universe/facts.json"
    assert fernhollow.docs == start.REPO_ROOT / "universe-electrical/docs"
    assert kestrel.index != fernhollow.index
    for business in (kestrel, fernhollow):
        assert business.facts.is_file() and business.docs.is_dir()


def test_rag_project_keeps_customer_questions_out_of_its_logs() -> None:
    env = start.rag_env(start.BUSINESSES["fernhollow"], {"PATH": "x", "RAG_LOG": "1"})
    assert env["RAG_LOG"] == "0" and env["RAG_WATCH"] == "0"
    assert env["RAG_DOCS_DIR"].endswith("docs") and "universe-electrical" in env["RAG_DOCS_DIR"]
    assert env["RAG_DB_DIR"].endswith("kb_index_electrical")
    assert env["PATH"] == "x"


def test_the_api_gets_the_chosen_business() -> None:
    env = start.api_env(start.BUSINESSES["fernhollow"], {"BUSINESS_FACTS_PATH": "other.json"})
    assert env["BUSINESS_FACTS_PATH"].endswith("facts.json")
    assert "universe-electrical" in env["BUSINESS_FACTS_PATH"]


def test_finding_rag_project_option_then_environment_then_sibling(tmp_path: Path) -> None:
    repo = tmp_path / "citedesk"
    repo.mkdir()
    sibling = make_rag(tmp_path / "rag-project")
    given = make_rag(tmp_path / "given")
    named = make_rag(tmp_path / "named")
    assert start.find_rag_project(str(given), {"RAG_PROJECT_DIR": str(named)}, repo) == given
    assert start.find_rag_project(None, {"RAG_PROJECT_DIR": str(named)}, repo) == named
    assert start.find_rag_project(None, {}, repo) == sibling
    assert start.find_rag_project(str(tmp_path / "nothing"), {}, repo) == sibling


def test_a_missing_rag_project_says_what_to_do(tmp_path: Path) -> None:
    with pytest.raises(start.StartError, match="--rag-project"):
        start.find_rag_project(None, {}, tmp_path / "citedesk")


def test_rag_project_needs_its_own_virtual_environment(tmp_path: Path) -> None:
    folder = make_rag(tmp_path / "rag", windows=False)
    assert start.rag_python(folder, windows=False) == folder / "venv/bin/python"
    with pytest.raises(start.StartError, match="virtual environment"):
        start.rag_python(folder, windows=True)


def test_npm_and_stopping_a_process_tree_per_platform() -> None:
    assert start.npm_command(windows=True)[0] == "npm.cmd"
    assert start.npm_command(windows=False) == ["npm", "run", "dev"]
    assert start.stop_command(42, windows=True) == ["taskkill", "/PID", "42", "/T", "/F"]
    assert start.stop_command(42, windows=False) is None


def test_ollama_must_have_both_models() -> None:
    both = {"models": [{"name": "qwen3:8b"}, {"name": "embeddinggemma:latest"}]}
    assert start.model_problem(both, "qwen3:8b") is None
    problem = start.model_problem({"models": [{"name": "qwen3:8b"}]}, "qwen3:8b")
    assert problem is not None and "embeddinggemma" in problem and "qwen3" not in problem
    assert start.model_problem({}, "qwen3:8b") is not None


def test_waiting_stops_when_ready_when_the_process_exits_or_when_time_is_up() -> None:
    now = [0.0]

    def clock() -> float:
        return now[0]

    def sleep(seconds: float) -> None:
        now[0] += seconds

    calls = iter([False, False, True])
    assert start.wait_until(lambda: next(calls), 10, sleep=sleep, clock=clock)

    now[0] = 0.0
    assert not start.wait_until(lambda: False, 10, alive=lambda: False, sleep=sleep, clock=clock)
    assert now[0] == 0.0  # gave up at once, without waiting out the time

    now[0] = 0.0
    assert not start.wait_until(lambda: False, 3, sleep=sleep, clock=clock)
    assert now[0] == pytest.approx(3.0)


def test_a_failed_step_stops_and_starts_nothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def no_ollama(settings: object, get: object = None) -> object:
        return type("C", (), {"status": "error", "reason": "unreachable"})()

    monkeypatch.setattr(start, "check_model", no_ollama)
    started: list[str] = []
    monkeypatch.setattr(start.Services, "start", lambda self, name, *a: started.append(name))
    assert start.main(["--no-web"]) == 1
    assert "Ollama is not answering" in capsys.readouterr().out
    assert started == []
