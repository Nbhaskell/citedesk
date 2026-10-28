"""Settings read from the environment and an optional .env file (names: docs/TRD.md section 7)."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    db_path: Path = Field(Path("data/citedesk.db"), validation_alias="CITEDESK_DB_PATH")
    port: int = Field(8100, ge=1, le=65535, validation_alias="CITEDESK_PORT")
    ollama_url: str = Field("http://127.0.0.1:11434", validation_alias="OLLAMA_URL")
    llm_model: str = Field("qwen3:8b", validation_alias="LLM_MODEL")
    rag_url: str = Field("http://127.0.0.1:8000", validation_alias="RAG_URL")
    escalate_on_low_confidence: bool = Field(True, validation_alias="ESCALATE_ON_LOW_CONFIDENCE")
    spam_threshold: float = Field(0.8, ge=0, le=1, validation_alias="SPAM_THRESHOLD")
    duplicate_window_hours: int = Field(24, ge=0, validation_alias="DUPLICATE_WINDOW_HOURS")
    max_body_chars: int = Field(10000, gt=0, validation_alias="MAX_BODY_CHARS")
    draft_max_words: int = Field(200, gt=0, validation_alias="DRAFT_MAX_WORDS")
    enable_thinking: bool = Field(False, validation_alias="ENABLE_THINKING")
    synthetic_data: bool = Field(True, validation_alias="SYNTHETIC_DATA")


SETTING_ENV_NAMES: tuple[str, ...] = tuple(
    str(field.validation_alias) for field in Settings.model_fields.values()
)
