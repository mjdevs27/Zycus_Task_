"""Application configuration for the US Delivery AI Support assignment."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or .env."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
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

    data_dir: Path = Field(default=Path("./data"), alias="DATA_DIR")
    tickets_file: Path = Field(
        default=Path("./data/tickets.json"), alias="TICKETS_FILE"
    )
    accounts_file: Path = Field(
        default=Path("./data/accounts.json"), alias="ACCOUNTS_FILE"
    )
    kb_dir: Path = Field(default=Path("./knowledge-base"), alias="KB_DIR")

    prompt_dir: Path = Field(default=Path("./prompts"), alias="PROMPT_DIR")
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
        default=Path("./eval_report.json"), alias="EVAL_REPORT_JSON"
    )
    eval_report_md: Path = Field(
        default=Path("./eval_report.md"), alias="EVAL_REPORT_MD"
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
