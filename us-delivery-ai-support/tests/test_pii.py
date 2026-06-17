"""Tests for app.pii — local PII redaction and data safety."""

from app.pii import (
    redact_account_payload,
    redact_pii,
    redact_ticket_payload,
)


def test_redact_email():
    text = "User john.doe@example.com cannot login."
    out = redact_pii(text)
    assert "[REDACTED_EMAIL]" in out
    assert "john.doe@example.com" not in out


def test_redact_email_with_plus_and_subdomain():
    out = redact_pii("Contact support+test@company.co.in please")
    assert "[REDACTED_EMAIL]" in out
    assert "support+test@company.co.in" not in out


def test_redact_phone_plain_ten_digits():
    out = redact_pii("Call me at 9876543210 today")
    assert "[REDACTED_PHONE]" in out
    assert "9876543210" not in out


def test_redact_phone_formatted():
    out = redact_pii("Reach me at (415) 555-1234 or 415-555-1234")
    assert "[REDACTED_PHONE]" in out
    assert "415-555-1234" not in out
    assert "(415) 555-1234" not in out


def test_redact_phone_international():
    out = redact_pii("My number is +91 98765 43210")
    assert "[REDACTED_PHONE]" in out
    assert "98765 43210" not in out


def test_redact_secrets():
    text = "api_key=abc123 token=secretvalue Bearer ey123abc"
    out = redact_pii(text)
    assert "[REDACTED_SECRET]" in out
    assert "abc123" not in out
    assert "secretvalue" not in out
    assert "ey123abc" not in out


def test_redact_openai_style_key():
    out = redact_pii("Key is sk-ABC123def456GHI789")
    assert "[REDACTED_SECRET]" in out
    assert "sk-ABC123def456GHI789" not in out


def test_redact_credit_card_like():
    out = redact_pii("Card 4111 1111 1111 1111 charged")
    assert "[REDACTED_CARD]" in out
    assert "4111 1111 1111 1111" not in out


def test_redact_ip_address():
    out = redact_pii("Server at 192.168.1.10 is down")
    assert "[REDACTED_IP]" in out
    assert "192.168.1.10" not in out


def test_redact_long_numeric_id():
    out = redact_pii("Account reference 1234567890123 noted")
    assert "[REDACTED" in out
    assert "1234567890123" not in out


def test_redact_sensitive_url_query():
    out = redact_pii("Reset via https://example.com/reset?token=abc123 now")
    assert "[REDACTED_QUERY]" in out or "[REDACTED_SECRET]" in out
    assert "abc123" not in out
    # domain/path preserved
    assert "https://example.com/reset" in out


def test_preserve_technical_codes():
    text = "Customer sees 500 error and 404 on retry. Marked P1."
    out = redact_pii(text)
    assert "500" in out
    assert "404" in out
    assert "P1" in out


def test_preserve_version_numbers():
    out = redact_pii("Upgrade to version 1.2.3 resolves it")
    assert "1.2.3" in out


def test_recursive_dictionary_redaction():
    payload = {
        "account": {
            "owner": "alice@example.com",
            "notes": ["Call +91 98765 43210"],
        }
    }
    out = redact_account_payload(payload)
    assert out["account"]["owner"] == "[REDACTED_EMAIL]"
    assert "[REDACTED_PHONE]" in out["account"]["notes"][0]
    # structure preserved
    assert isinstance(out["account"]["notes"], list)


def test_ticket_payload_redaction_does_not_mutate_input():
    payload = {"subject": "Login issue for john@example.com", "body": "Call 9876543210"}
    original = {"subject": payload["subject"], "body": payload["body"]}
    out = redact_ticket_payload(payload)
    assert out["subject"] == "Login issue for [REDACTED_EMAIL]"
    assert "[REDACTED_PHONE]" in out["body"]
    # original untouched
    assert payload == original


def test_payload_preserves_non_string_values():
    payload = {"priority": 1, "score": 0.5, "open": True, "tags": None}
    out = redact_ticket_payload(payload)
    assert out["priority"] == 1
    assert out["score"] == 0.5
    assert out["open"] is True
    assert out["tags"] is None


def test_none_handling():
    assert redact_pii(None) == ""


def test_empty_and_whitespace_handling():
    assert redact_pii("") == ""
    assert redact_pii("   ") == "   "


def test_redaction_is_deterministic():
    text = "Email a@b.com phone 9876543210"
    assert redact_pii(text) == redact_pii(text)
