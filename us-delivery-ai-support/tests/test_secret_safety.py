"""Tests for the local secret scanner (scripts/check_secrets.py)."""

from __future__ import annotations

from scripts.check_secrets import (
    is_ignored_path,
    is_placeholder_value,
    redact_secret,
    scan_text,
)


# Test 1 — placeholder allowed
def test_placeholder_allowed():
    assert scan_text("OPENAI_API_KEY=your_api_key_here") == []
    assert is_placeholder_value("your_api_key_here") is True


# Test 2 — Groq key detected. The fixture key below is FAKE (random-looking, not
# an alphabet walk) and the line is allow-listed so the repo scan skips it.
def test_groq_key_detected():
    fake_groq = "gsk_7Hk29ZpQ4mTxR8vB1nL6wY3aF5dC0jE"  # allowlist-secret (fake)
    findings = scan_text(f"OPENAI_API_KEY={fake_groq}")
    assert findings, "expected a violation for a real Groq key"


# Test 3 — OpenAI key detected
def test_openai_key_detected():
    fake_openai = "sk-7Hk29ZpQ4mTxR8vB1nL6wY3aF5dC0jE"  # allowlist-secret (fake)
    findings = scan_text(f"OPENAI_API_KEY={fake_openai}")
    assert findings, "expected a violation for a real OpenAI key"


# Test 4 — redaction hides full key
def test_redaction_hides_full_key():
    secret = "gsk_7Hk29ZpQ4mTxR8vB1nL6wY3aF5dC0jE"  # allowlist-secret (fake)
    preview = redact_secret(secret)
    assert preview.startswith("gsk_")
    assert preview.endswith("0jE")
    assert secret not in preview
    assert "****" in preview


# Test 5 — ignored paths skipped
def test_ignored_paths_skipped():
    assert is_ignored_path(".venv/file.py") is True
    assert is_ignored_path("__pycache__/x.pyc") is True
    assert is_ignored_path("logo.png") is True
    assert is_ignored_path("app/main.py") is False
