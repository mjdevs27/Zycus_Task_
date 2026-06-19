"""Tests for app.config settings."""

from pathlib import Path

from app.config import PROJECT_ROOT, Settings


def test_settings_defaults_are_available():
    settings = Settings()
    assert settings.openai_model
    assert settings.app_port == 8000
    assert isinstance(settings.tickets_file, Path)
    assert isinstance(settings.accounts_file, Path)
    assert isinstance(settings.kb_dir, Path)
    assert settings.llm_temperature == 0


def test_data_paths_are_anchored_to_project_root():
    # Paths must be absolute and rooted at the project so the app works no
    # matter which working directory it is launched from (e.g. Streamlit Cloud).
    settings = Settings()
    for path in (
        settings.data_dir,
        settings.tickets_file,
        settings.accounts_file,
        settings.kb_dir,
        settings.prompt_dir,
        settings.eval_report_json,
        settings.eval_report_md,
    ):
        assert path.is_absolute()
        assert str(path).startswith(str(PROJECT_ROOT))


def test_relative_path_override_is_anchored(monkeypatch):
    # A relative override (as set in .env, e.g. ./knowledge-base) must be
    # resolved against the project root, not the current working directory.
    monkeypatch.setenv("KB_DIR", "./knowledge-base")
    settings = Settings()
    assert settings.kb_dir.is_absolute()
    assert settings.kb_dir == (PROJECT_ROOT / "knowledge-base").resolve()
