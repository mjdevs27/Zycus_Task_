"""Tests for app.config settings."""

from pathlib import Path

from app.config import Settings


def test_settings_defaults_are_available():
    settings = Settings()
    assert settings.openai_model
    assert settings.app_port == 8000
    assert isinstance(settings.tickets_file, Path)
    assert isinstance(settings.accounts_file, Path)
    assert isinstance(settings.kb_dir, Path)
    assert settings.llm_temperature == 0
