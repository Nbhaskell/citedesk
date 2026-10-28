import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def is_ignored(path: str) -> bool:
    result = subprocess.run(  # noqa: S603
        ["git", "check-ignore", "--quiet", "--no-index", path],  # noqa: S607
        cwd=REPO_ROOT,
        check=False,
    )
    return result.returncode == 0


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        ".env.local",
        "data/citedesk.db",
        "citedesk.db",
        "citedesk.db-wal",
        "citedesk.db-shm",
        "something.sqlite",
        ".venv/Scripts/python.exe",
        "web/node_modules/react/index.js",
        "eval/runs/run-1.run.json",
        "CLAUDE.local.md",
    ],
)
def test_sensitive_and_generated_paths_are_git_ignored(path: str) -> None:
    assert is_ignored(path), f"{path} must be git-ignored"


@pytest.mark.parametrize(
    "path",
    [
        ".env.example",
        "eval/runs/.gitkeep",
        "eval/reports/report.md",
        "eval/golden/citedesk_v1.json",
        "db/migrations/0001_init.sql",
        "docs/DECISIONS.md",
        ".gitleaks.toml",
        "requirements.lock",
    ],
)
def test_published_paths_are_not_ignored(path: str) -> None:
    assert not is_ignored(path), f"{path} must not be git-ignored"
