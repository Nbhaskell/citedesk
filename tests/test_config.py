from pathlib import Path

import pytest
from pydantic import ValidationError

from citedesk.config import SETTING_ENV_NAMES, Settings

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_defaults_match_the_documented_stack() -> None:
    s = Settings(_env_file=None)
    assert s.port == 8100
    assert s.llm_model == "qwen3:8b"
    assert s.rag_url == "http://127.0.0.1:8000"
    assert s.ollama_url == "http://127.0.0.1:11434"
    assert s.escalate_on_low_confidence is True
    assert s.enable_thinking is False
    assert s.synthetic_data is True
    assert s.db_path == Path("data/citedesk.db")


def test_environment_overrides_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CITEDESK_PORT", "9001")
    monkeypatch.setenv("LLM_MODEL", "other-model")
    monkeypatch.setenv("ENABLE_THINKING", "true")
    monkeypatch.setenv("SYNTHETIC_DATA", "false")
    monkeypatch.setenv("CITEDESK_DB_PATH", "somewhere/else.db")
    s = Settings(_env_file=None)
    assert s.port == 9001
    assert s.llm_model == "other-model"
    assert s.enable_thinking is True
    assert s.synthetic_data is False
    assert s.db_path == Path("somewhere/else.db")


def test_env_file_is_read(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("CITEDESK_PORT=9100\nRAG_URL=http://127.0.0.1:8123\n", encoding="utf-8")
    s = Settings(_env_file=env_file)
    assert s.port == 9100
    assert s.rag_url == "http://127.0.0.1:8123"


def test_unknown_env_file_keys_are_ignored(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("SOMETHING_ELSE=1\n", encoding="utf-8")
    Settings(_env_file=env_file)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("CITEDESK_PORT", "0"),
        ("CITEDESK_PORT", "70000"),
        ("CITEDESK_PORT", "not-a-number"),
        ("SPAM_THRESHOLD", "-0.1"),
        ("SPAM_THRESHOLD", "1.5"),
        ("DRAFT_MAX_WORDS", "0"),
        ("ENABLE_THINKING", "maybe"),
    ],
)
def test_invalid_values_are_rejected(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def _env_example_entries() -> dict[str, str]:
    entries: dict[str, str] = {}
    for raw in (REPO_ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        entries[key.strip()] = value.strip()
    return entries


def test_env_example_lists_every_setting_and_nothing_else() -> None:
    assert set(_env_example_entries()) == set(SETTING_ENV_NAMES)


def test_env_example_values_equal_the_defaults() -> None:
    from_example = Settings(_env_file=REPO_ROOT / ".env.example")
    assert from_example == Settings(_env_file=None)


def test_env_example_holds_no_secrets() -> None:
    # Phase 0 has no secrets at all; if one is ever added, this test must be revisited on purpose.
    lowered = " ".join(_env_example_entries()).lower()
    for word in ("key", "token", "password", "secret"):
        assert word not in lowered


def test_the_fact_sheet_path_defaults_to_the_invented_business() -> None:
    assert Settings(_env_file=None).business_facts_path == Path("universe/facts.json")
