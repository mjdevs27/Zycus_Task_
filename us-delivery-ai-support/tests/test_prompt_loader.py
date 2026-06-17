"""Tests for app.prompt_loader — prompt versioning and rendering."""

import pytest

from app.prompt_loader import (
    PromptNotFoundError,
    PromptRenderError,
    get_prompt_version,
    load_prompt,
    parse_prompt_metadata,
    render_prompt,
)


def test_load_existing_prompt_returns_non_empty():
    text = load_prompt("triage_v1")
    assert isinstance(text, str)
    assert text.strip()


def test_load_prompt_missing_raises():
    with pytest.raises(PromptNotFoundError):
        load_prompt("does_not_exist_v9")


def test_parse_metadata_fields():
    text = load_prompt("triage_v1")
    metadata = parse_prompt_metadata(text)
    assert metadata["prompt_name"] == "triage_agent"
    assert metadata["version"] == "triage_v1"
    assert metadata["task"] == "intelligent_ticket_triage"


def test_render_prompt_replaces_variables():
    assert render_prompt("Hello {{name}}", {"name": "Moksh"}) == "Hello Moksh"


def test_render_prompt_ignores_extra_variables():
    out = render_prompt("Hi {{name}}", {"name": "A", "unused": "B"})
    assert out == "Hi A"


def test_render_prompt_missing_variable_raises():
    with pytest.raises(PromptRenderError):
        render_prompt("Ticket: {{ticket_text}}", {})


def test_get_prompt_version():
    assert get_prompt_version("triage_v1") == "triage_v1"
    assert get_prompt_version("account_summary_v1") == "account_summary_v1"
    assert get_prompt_version("judge_v1") == "judge_v1"


def test_triage_prompt_contains_required_placeholders():
    text = load_prompt("triage_v1")
    assert "{{ticket_text}}" in text
    assert "{{retrieved_kb_docs}}" in text
    assert "{{prompt_version}}" in text
