"""Tests for app.llm_client — abstraction, parsing, and determinism.

These tests never call the real OpenAI API. They exercise configuration
behavior and the pure JSON-parsing helpers.
"""

import pytest

from app.config import Settings
from app.llm_client import (
    LLMClient,
    LLMJSONParseError,
    LLMResponseError,
    MissingLLMConfigurationError,
    extract_json_object,
    strip_json_fences,
    validate_model_response_text,
)


def _keyless_settings(monkeypatch) -> Settings:
    """Settings guaranteed to have no API key (ignores .env and env vars)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return Settings(_env_file=None)


def test_missing_api_key_not_configured(monkeypatch):
    client = LLMClient(api_key=None, settings=_keyless_settings(monkeypatch))
    assert client.is_configured() is False


def test_missing_api_key_raises_on_call(monkeypatch):
    client = LLMClient(api_key=None, settings=_keyless_settings(monkeypatch))
    with pytest.raises(MissingLLMConfigurationError):
        client.complete_text("hello")
    with pytest.raises(MissingLLMConfigurationError):
        client.complete_json("hello")


def test_strip_json_fences():
    fenced = '```json\n{"urgency_tier": "P1"}\n```'
    assert strip_json_fences(fenced) == '{"urgency_tier": "P1"}'


def test_extract_json_object_from_surrounding_text():
    text = "Here is the result: {\"a\": 1, \"b\": 2}\nThanks."
    extracted = extract_json_object(text)
    assert extracted == '{"a": 1, "b": 2}'


def test_parse_json_response_with_fences():
    parsed = LLMClient.parse_json_response('```json\n{"x": 1}\n```')
    assert parsed == {"x": 1}


def test_parse_json_response_with_extra_text():
    parsed = LLMClient.parse_json_response('Result: {"a": 1, "b": 2} done')
    assert parsed == {"a": 1, "b": 2}


def test_invalid_json_raises():
    with pytest.raises(LLMJSONParseError):
        LLMClient.parse_json_response("no json here at all")


def test_empty_response_raises():
    with pytest.raises(LLMResponseError):
        validate_model_response_text("   ")


def test_deterministic_defaults():
    client = LLMClient(api_key="test")
    assert client.temperature == 0
    assert client.seed == 42
    assert client.is_configured() is True


def test_nested_json_object_extraction():
    text = 'prefix {"outer": {"inner": [1, 2]}, "k": "}"} suffix'
    extracted = extract_json_object(text)
    assert extracted == '{"outer": {"inner": [1, 2]}, "k": "}"}'
