"""Application configuration for the US Delivery AI Support assignment."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Absolute project root (the directory that contains app/, data/, prompts/,
# knowledge-base/ and .env). Anchoring the .env path and all default data paths
# to this root makes configuration independent of the current working
# directory, so the app behaves identically whether launched from the project
# root (``python run.py``), the repository root, or by Streamlit Cloud.
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or .env."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    # Base URL for the OpenAI-compatible endpoint. Leave unset for OpenAI itself,
    # or point it at a compatible provider such as Groq
    # (https://api.groq.com/openai/v1).
    openai_base_url: str | None = Field(default=None, alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    llm_temperature: float = Field(default=0.0, alias="LLM_TEMPERATURE")
    llm_seed: int = Field(default=42, alias="LLM_SEED")

    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")

    data_dir: Path = Field(default=PROJECT_ROOT / "data", alias="DATA_DIR")
    tickets_file: Path = Field(
        default=PROJECT_ROOT / "data" / "tickets.json", alias="TICKETS_FILE"
    )
    accounts_file: Path = Field(
        default=PROJECT_ROOT / "data" / "accounts.json", alias="ACCOUNTS_FILE"
    )
    kb_dir: Path = Field(default=PROJECT_ROOT / "knowledge-base", alias="KB_DIR")

    prompt_dir: Path = Field(default=PROJECT_ROOT / "prompts", alias="PROMPT_DIR")
    triage_prompt_version: str = Field(
        default="triage_v1", alias="TRIAGE_PROMPT_VERSION"
    )
    account_prompt_version: str = Field(
        default="account_summary_v1", alias="ACCOUNT_PROMPT_VERSION"
    )
    judge_prompt_version: str = Field(
        default="judge_v1", alias="JUDGE_PROMPT_VERSION"
    )

    top_k_kb_docs: int = Field(default=3, alias="TOP_K_KB_DOCS")

    eval_report_json: Path = Field(
        default=PROJECT_ROOT / "eval_report.json", alias="EVAL_REPORT_JSON"
    )
    eval_report_md: Path = Field(
        default=PROJECT_ROOT / "eval_report.md", alias="EVAL_REPORT_MD"
    )

    @field_validator(
        "data_dir",
        "tickets_file",
        "accounts_file",
        "kb_dir",
        "prompt_dir",
        "eval_report_json",
        "eval_report_md",
        mode="after",
    )
    @classmethod
    def _anchor_relative_paths(cls, value: Path) -> Path:
        """Resolve relative paths against the project root.

        Values may arrive as relative paths from .env (e.g. ``./knowledge-base``)
        or Streamlit secrets. Anchoring them to ``PROJECT_ROOT`` keeps the app
        working regardless of the current working directory.
        """
        if value is None:
            return value
        return value if value.is_absolute() else (PROJECT_ROOT / value).resolve()


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()


def is_llm_configured() -> bool:
    """Return True when an LLM API key is configured (without exposing it)."""
    return bool(get_settings().openai_api_key)
