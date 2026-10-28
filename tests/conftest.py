import pytest

from citedesk.config import SETTING_ENV_NAMES


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the developer's real environment out of every test."""
    for name in SETTING_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
