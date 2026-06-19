"""Local, deterministic PII redaction and data-safety utilities.

This module provides lightweight, rule-based redaction that runs *before* any
ticket or account text is sent to an external LLM provider. It is intentionally
local and dependency-free:

    Raw ticket/account text -> redact_pii() -> LLM prompt construction

It deliberately preserves useful technical signals (HTTP status codes, priority
tiers like P1-P4, short version numbers) so support triage quality is not lost.
"""

from __future__ import annotations

import re
from typing import Any

# Redaction placeholders -----------------------------------------------------

EMAIL_TOKEN = "[REDACTED_EMAIL]"
PHONE_TOKEN = "[REDACTED_PHONE]"
NUMERIC_ID_TOKEN = "[REDACTED_NUMERIC_ID]"
SECRET_TOKEN = "[REDACTED_SECRET]"
CARD_TOKEN = "[REDACTED_CARD]"
IP_TOKEN = "[REDACTED_IP]"
QUERY_TOKEN = "[REDACTED_QUERY]"


# Compiled patterns ----------------------------------------------------------

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# Secrets: key=value style assignments for common secret-bearing key names.
_SECRET_KEYVALUE_RE = re.compile(
    r"(?i)\b(api[_-]?key|apikey|token|access[_-]?token|refresh[_-]?token"
    r"|client[_-]?secret|secret|password|passwd|pwd)\b\s*[:=]\s*\S+"
)
# Bearer tokens.
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]+")
# OpenAI-style keys: sk-XXXX...
_SK_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9]{8,}\b")

# Credit-card-like: 13-19 digits, optionally separated by single spaces/hyphens.
_CARD_RE = re.compile(r"(?<![\w])(?:\d[ -]?){12,18}\d(?![\w])")

# IPv4 addresses.
_IP_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")

# URLs with a query string; capture scheme/host/path and the query separately.
_URL_QUERY_RE = re.compile(r"(https?://[^\s?]+)\?(\S+)")

# Phone-like runs: optional leading +, then 10-15 digits separated only by
# single spaces, dots, hyphens or parentheses. Requires >= 10 digits so short
# numbers (404, 500, P1, 1.2.3) are never matched. A trailing period is allowed
# (sentence punctuation) but a period followed by a digit is rejected so dotted
# versions / decimals are preserved.
_PHONE_RE = re.compile(r"(?<![\w@.+])\(?\+?(?:\d[\s.\-()]{0,2}){9,14}\d(?![\w@]|\.\d)")

# Long standalone numeric identifiers: 8+ contiguous digits, not part of a
# dotted version or alphanumeric token. A trailing sentence period is allowed,
# but a period followed by a digit (version/decimal) is not.
_LONG_NUMERIC_RE = re.compile(r"(?<![\w.])\d{8,}(?![\w]|\.\d)")


# Single-target redactors ----------------------------------------------------


def redact_email(text: str) -> str:
    """Replace email addresses with ``[REDACTED_EMAIL]``."""
    return _EMAIL_RE.sub(EMAIL_TOKEN, text)


def redact_phone(text: str) -> str:
    """Replace phone-like numbers with ``[REDACTED_PHONE]``.

    Short numbers (HTTP codes, priorities, version numbers) are preserved
    because at least ten digits are required to match.
    """
    return _PHONE_RE.sub(PHONE_TOKEN, text)


def redact_long_numeric_ids(text: str) -> str:
    """Replace standalone numeric sequences of 8+ digits."""
    return _LONG_NUMERIC_RE.sub(NUMERIC_ID_TOKEN, text)


def redact_possible_secrets(text: str) -> str:
    """Replace common secret patterns (keys, tokens, passwords, bearer)."""
    text = _SECRET_KEYVALUE_RE.sub(lambda m: f"{m.group(1)}={SECRET_TOKEN}", text)
    text = _BEARER_RE.sub(f"Bearer {SECRET_TOKEN}", text)
    text = _SK_KEY_RE.sub(SECRET_TOKEN, text)
    return text


def redact_credit_card_like(text: str) -> str:
    """Replace credit-card-like digit runs (13-19 digits)."""
    return _CARD_RE.sub(CARD_TOKEN, text)


def redact_ip_addresses(text: str) -> str:
    """Replace IPv4 addresses with ``[REDACTED_IP]``."""
    return _IP_RE.sub(IP_TOKEN, text)


def redact_sensitive_urls(text: str) -> str:
    """Redact the query string of any URL, keeping the domain/path intact."""
    return _URL_QUERY_RE.sub(rf"\1?{QUERY_TOKEN}", text)


# Main entry points ----------------------------------------------------------


def redact_pii(text: str | None) -> str:
    """Apply all redactors in a stable, deterministic order.

    Returns an empty string for ``None`` and is safe for empty/whitespace input.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)

    # Order matters: secrets and URLs first (they own '=' / '?' context),
    # then card runs, emails, IPs, phones, and finally any leftover long IDs.
    text = redact_possible_secrets(text)
    text = redact_sensitive_urls(text)
    text = redact_credit_card_like(text)
    text = redact_email(text)
    text = redact_ip_addresses(text)
    text = redact_phone(text)
    text = redact_long_numeric_ids(text)
    return text


def _redact_value(value: Any) -> Any:
    """Recursively redact strings inside dicts/lists; leave other types as-is."""
    if value is None:
        return None
    if isinstance(value, str):
        return redact_pii(value)
    if isinstance(value, dict):
        return {key: _redact_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(item) for item in value)
    return value


def redact_ticket_payload(payload: dict | None) -> dict:
    """Return a new dict with all string values redacted. Input is not mutated."""
    if payload is None:
        return {}
    return {key: _redact_value(value) for key, value in payload.items()}


def redact_account_payload(payload: dict | None) -> dict:
    """Return a new dict with all string values redacted. Input is not mutated."""
    if payload is None:
        return {}
    return {key: _redact_value(value) for key, value in payload.items()}
