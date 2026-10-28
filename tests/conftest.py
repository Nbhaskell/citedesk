from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from citedesk.api import create_app
from citedesk.config import SETTING_ENV_NAMES, Settings


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the developer's real environment out of every test."""
    for name in SETTING_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def api_settings(tmp_path: Path) -> Settings:
    """Settings for an API test: a database file of its own."""
    return Settings(_env_file=None, db_path=tmp_path / "api.db")


@pytest.fixture
def client(api_settings: Settings) -> Iterator[TestClient]:
    """An API client with the database migrated and the background worker off.

    Server errors come back as 500 responses instead of being raised, as they would for a caller.
    """
    app = create_app(api_settings, start_worker=False)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
