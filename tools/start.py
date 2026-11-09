"""Start the whole demo with one command (D-102).

    python -m tools.start [--business kestrel|fernhollow] [--rag-project PATH] [--no-web]

In order, each step said in one line:
1. **Ollama** must already be running with the chat model (`LLM_MODEL`) and `embeddinggemma`. This
   command does not start it: it is a system service.
2. **rag-project** on 127.0.0.1:8000. If it already answers, it is used only if its passages are
   the chosen business's (the same check as the evaluation runner, D-100); otherwise it is started
   from its folder on that business's documents, with its own index folder, `RAG_LOG=0` (no
   customer-derived questions in its logs) and `RAG_WATCH=0`, and indexed if its index is empty.
3. **The Citedesk API** on 127.0.0.1:8100 with that business's fact sheet. If something already
   answers there, the command stops: it cannot tell which business that API was started for.
4. **The web app** on 127.0.0.1:5174 (`npm run dev` in `web/`, which needs `npm ci` once).

Ctrl+C stops what this command started, newest first, and nothing else. If a started service
exits on its own, the others are stopped too. The rag-project folder comes from `--rag-project`,
then `RAG_PROJECT_DIR`, then a `rag-project` folder next to this repository.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from citedesk.business import load_business
from citedesk.config import Settings
from citedesk.health import check_knowledge_base, check_model, http_get_json
from citedesk.knowledge import RagProjectKB

REPO_ROOT = Path(__file__).resolve().parent.parent
EMBED_MODEL = "embeddinggemma"
WEB_URL = "http://127.0.0.1:5174"
RAG_START_SECONDS = 120.0
API_START_SECONDS = 60.0
WEB_START_SECONDS = 60.0
REINDEX_SECONDS = 600.0


@dataclass(frozen=True)
class Business:
    """One invented business: its fact sheet, its documents and rag-project's index folder."""

    key: str
    universe: Path
    index: Path

    @property
    def facts(self) -> Path:
        return self.universe / "facts.json"

    @property
    def docs(self) -> Path:
        return self.universe / "docs"


BUSINESSES: dict[str, Business] = {
    "kestrel": Business("kestrel", REPO_ROOT / "universe", REPO_ROOT / "data/kb_index"),
    "fernhollow": Business(
        "fernhollow", REPO_ROOT / "universe-electrical", REPO_ROOT / "data/kb_index_electrical"
    ),
}


class StartError(Exception):
    """A step cannot go ahead. The message says what to do."""


# --- plain decisions (unit-tested) ------------------------------------------------------------


def find_rag_project(given: str | None, env: Mapping[str, str], repo_root: Path) -> Path:
    """The rag-project folder: the option, then RAG_PROJECT_DIR, then a sibling folder."""
    for candidate in (given, env.get("RAG_PROJECT_DIR"), str(repo_root.parent / "rag-project")):
        if candidate and (Path(candidate) / "chat.py").is_file():
            return Path(candidate)
    raise StartError(
        "rag-project was not found. Pass --rag-project <folder> or set RAG_PROJECT_DIR "
        "(the folder that holds chat.py)."
    )


def rag_python(folder: Path, windows: bool) -> Path:
    """rag-project's own interpreter, in its `venv` folder."""
    python = folder / ("venv/Scripts/python.exe" if windows else "venv/bin/python")
    if not python.is_file():
        raise StartError(f"rag-project has no virtual environment at {python}; set it up first.")
    return python


def rag_env(business: Business, base: Mapping[str, str]) -> dict[str, str]:
    return {
        **base,
        "RAG_DOCS_DIR": str(business.docs),
        "RAG_DB_DIR": str(business.index),
        "RAG_LOG": "0",  # keeps customer-derived questions out of its logs
        "RAG_WATCH": "0",  # index only when asked
    }


def api_env(business: Business, base: Mapping[str, str]) -> dict[str, str]:
    return {**base, "BUSINESS_FACTS_PATH": str(business.facts)}


def npm_command(windows: bool) -> list[str]:
    return ["npm.cmd" if windows else "npm", "run", "dev"]


def stop_command(pid: int, windows: bool) -> list[str] | None:
    """On Windows a service's children (npm starts node) are stopped with its whole tree."""
    return ["taskkill", "/PID", str(pid), "/T", "/F"] if windows else None


def model_problem(tags: Mapping[str, Any], chat_model: str) -> str | None:
    """None if Ollama has both models, otherwise what to do."""
    models = tags.get("models")
    names: set[str] = set()
    if isinstance(models, list):
        for m in models:
            if isinstance(m, dict):
                names |= {str(m.get("name")), str(m.get("model"))}
    missing = [
        wanted
        for wanted in (chat_model, EMBED_MODEL)
        if wanted not in names and f"{wanted}:latest" not in names
    ]
    return f"Ollama is missing {', '.join(missing)}: run `ollama pull <name>`." if missing else None


def wait_until(
    ready: Callable[[], bool],
    seconds: float,
    *,
    alive: Callable[[], bool] = lambda: True,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> bool:
    """Poll `ready` until it is true, the time is up, or the process it waits for has exited."""
    deadline = clock() + seconds
    while clock() < deadline:
        if ready():
            return True
        if not alive():
            return False
        sleep(0.5)
    return ready()


# --- side effects ------------------------------------------------------------------------------


def answers(url: str) -> bool:
    try:
        http_get_json(url, 2.0)
    except Exception:  # noqa: BLE001 (any failure means it does not answer)
        return False
    return True


def page_answers(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2.0) as response:  # noqa: S310 (loopback)
            return bool(response.status == 200)
    except (urllib.error.URLError, OSError):
        return False


def post_json(url: str, body: dict[str, Any], seconds: float) -> dict[str, Any]:
    request = urllib.request.Request(  # noqa: S310 (loopback only)
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=seconds) as response:  # noqa: S310
        parsed = json.loads(response.read())
    return parsed if isinstance(parsed, dict) else {}


def say(text: str) -> None:
    print(text, flush=True)


@dataclass
class Services:
    """What this command started, newest last, so it can stop exactly those."""

    windows: bool = sys.platform == "win32"
    started: list[tuple[str, subprocess.Popen[bytes]]] = field(default_factory=list)

    def start(self, name: str, command: Sequence[str], cwd: Path, env: Mapping[str, str]) -> Any:
        process = subprocess.Popen(  # noqa: S603 (fixed commands, no shell)
            list(command),
            cwd=cwd,
            env=dict(env),
            start_new_session=not self.windows,
        )
        self.started.append((name, process))
        return process

    def exited(self) -> str | None:
        for name, process in self.started:
            if process.poll() is not None:
                return name
        return None

    def stop_all(self) -> None:
        for name, process in reversed(self.started):
            if process.poll() is not None:
                continue
            command = stop_command(process.pid, self.windows)
            if command:
                subprocess.run(command, capture_output=True, check=False)  # noqa: S603
            else:
                os.killpg(process.pid, 15)  # type: ignore[attr-defined,unused-ignore]
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
            say(f"Stopped {name}.")
        self.started.clear()


def start_knowledge_base(
    services: Services, business: Business, settings: Settings, rag_folder: str | None
) -> None:
    facts = load_business(business.facts)
    kb = RagProjectKB(settings.rag_url)
    from tools.eval_run import kb_serves  # the runner's check that passages are this business's

    status = check_knowledge_base(settings)
    if status.reason == "unreachable":
        folder = find_rag_project(rag_folder, os.environ, REPO_ROOT)
        say(f"Starting rag-project on {business.docs.relative_to(REPO_ROOT)} ...")
        process = services.start(
            "rag-project",
            [str(rag_python(folder, services.windows)), "chat.py", "--no-browser"],
            folder,
            rag_env(business, os.environ),
        )
        url = settings.rag_url.rstrip("/") + "/api/status"
        if not wait_until(
            lambda: answers(url), RAG_START_SECONDS, alive=lambda: process.poll() is None
        ):
            raise StartError("rag-project did not start; read its output above.")
        status = check_knowledge_base(settings)
        if status.reason == "not_indexed":
            say("Indexing the documents (the first time takes a few minutes) ...")
            post_json(settings.rag_url.rstrip("/") + "/api/reindex", {}, REINDEX_SECONDS)
            status = check_knowledge_base(settings)
    else:
        say("rag-project is already running; checking which documents it serves ...")
    if status.status != "ok":
        raise StartError(f"rag-project is not ready ({status.reason}).")
    problem = kb_serves(kb, facts)
    if problem:
        raise StartError(
            f"{problem}. Or stop the rag-project that is running and run this command again: it "
            "then starts one on the right documents."
        )
    say(f"rag-project serves {facts.name}.")


def run(args: argparse.Namespace) -> int:
    business = BUSINESSES[args.business]
    settings = Settings().model_copy(update={"business_facts_path": business.facts})
    services = Services()
    api_url = f"http://127.0.0.1:{settings.port}"
    try:
        say("Checking Ollama ...")
        if check_model(settings).reason in ("unreachable", "not_local", "bad_response"):
            raise StartError("Ollama is not answering. Start it, then try again.")
        problem = model_problem(http_get_json(settings.ollama_url.rstrip("/") + "/api/tags", 2.0),
                                settings.llm_model)  # fmt: skip
        if problem:
            raise StartError(problem)

        start_knowledge_base(services, business, settings, args.rag_project)

        if answers(api_url + "/api/status"):
            raise StartError(
                f"Something already answers on {api_url}. Stop that Citedesk API first: this "
                "command cannot tell which business it was started for."
            )
        say("Starting the Citedesk API ...")
        api = services.start(
            "the API", [sys.executable, "-m", "citedesk"], REPO_ROOT, api_env(business, os.environ)
        )
        if not wait_until(lambda: answers(api_url + "/api/status"), API_START_SECONDS,
                          alive=lambda: api.poll() is None):  # fmt: skip
            raise StartError("The API did not start; read its output above.")

        if not args.no_web:
            web = REPO_ROOT / "web"
            if not (web / "node_modules").is_dir():
                raise StartError("The web app is not installed: run `npm ci` in web\\ once.")
            say("Starting the web app ...")
            vite = services.start("the web app", npm_command(services.windows), web, os.environ)
            if not wait_until(lambda: page_answers(WEB_URL), WEB_START_SECONDS,
                              alive=lambda: vite.poll() is None):  # fmt: skip
                raise StartError("The web app did not start; read its output above.")

        say("")
        say(f"Citedesk is running for {load_business(business.facts).name} (invented data).")
        say(f"Open {WEB_URL if not args.no_web else api_url + '/api/status'}")
        say("Press Ctrl+C to stop everything this command started.")
        while (gone := services.exited()) is None:
            time.sleep(1)
        say(f"{gone} stopped on its own; stopping the rest.")
        return 1
    except StartError as error:
        say(f"Cannot start: {error}")
        return 1
    except KeyboardInterrupt:
        say("Stopping ...")
        return 0
    finally:
        services.stop_all()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--business", choices=sorted(BUSINESSES), default="kestrel")
    parser.add_argument("--rag-project", help="rag-project's folder (the one with chat.py)")
    parser.add_argument("--no-web", action="store_true", help="start everything but the web app")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
