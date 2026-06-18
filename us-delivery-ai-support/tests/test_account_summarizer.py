"""Tests for Task 2 — TAM account health summariser.

All tests use tiny in-test objects and fakes. No official dataset and no real
LLM API key are required.
"""

from __future__ import annotations

import pytest

from app.account_summarizer import (
    AccountHealthSummarizer,
    AccountNotFoundError,
    detect_risk_quote_candidates,
    filter_tickets_last_90_days,
    find_account_by_id,
    post_process_brief_response,
    sanitize_risk_flags,
    ticket_matches_account,
    verify_evidence_quote,
)
from app.llm_client import LLMClient, MissingLLMConfigurationError
from app.schemas import AccountBriefResponse


# ---------------------------------------------------------------------------
# Test 1 — flexible account lookup
# ---------------------------------------------------------------------------


def test_find_account_by_id_supports_flexible_keys():
    accounts = [
        {"account_id": "A1", "name": "one"},
        {"id": "B2", "name": "two"},
        {"customer_id": "C3", "name": "three"},
    ]
    assert find_account_by_id(accounts, "A1")["name"] == "one"
    assert find_account_by_id(accounts, "B2")["name"] == "two"
    assert find_account_by_id(accounts, "C3")["name"] == "three"


def test_find_account_by_id_raises_when_not_found():
    with pytest.raises(AccountNotFoundError):
        find_account_by_id([{"account_id": "A1"}], "missing")


# ---------------------------------------------------------------------------
# Test 2 — flexible ticket matching
# ---------------------------------------------------------------------------


def test_ticket_matches_account_supports_flexible_keys():
    assert ticket_matches_account({"account_id": "A1"}, "A1") is True
    assert ticket_matches_account({"customer_id": "A1"}, "A1") is True
    assert ticket_matches_account({"accountId": "A1"}, "A1") is True
    assert ticket_matches_account({"account_id": "OTHER"}, "A1") is False
    assert ticket_matches_account({"unrelated": "A1"}, "A1") is False


# ---------------------------------------------------------------------------
# Test 3 — last 90 days filtering
# ---------------------------------------------------------------------------


def test_filter_tickets_last_90_days_uses_latest_date_as_reference():
    tickets = [
        {"ticket_id": "t_latest", "created_at": "2026-06-18"},
        {"ticket_id": "t_recent", "created_at": "2026-06-08"},  # 10 days before
        {"ticket_id": "t_old", "created_at": "2026-03-10"},  # 100 days before
    ]
    kept = filter_tickets_last_90_days(tickets)
    kept_ids = {t["ticket_id"] for t in kept}
    assert "t_recent" in kept_ids
    assert "t_old" not in kept_ids


# ---------------------------------------------------------------------------
# Test 4 — risk candidate detection
# ---------------------------------------------------------------------------


def test_detect_risk_quote_candidates_finds_churn_signal():
    tickets = [
        {
            "ticket_id": "t1",
            "body": "If this is not fixed before renewal, we may cancel.",
        }
    ]
    candidates = detect_risk_quote_candidates(tickets)
    assert len(candidates) == 1
    assert candidates[0]["signal"] == "churn_risk"
    assert candidates[0]["quote"] == "If this is not fixed before renewal, we may cancel."


# ---------------------------------------------------------------------------
# Test 5 — quote verification rejects invented quote
# ---------------------------------------------------------------------------


def test_verify_evidence_quote_rejects_invented_quote():
    tickets = [{"ticket_id": "t1", "body": "The dashboard is slow."}]
    found, ticket_id = verify_evidence_quote("We will cancel tomorrow.", tickets)
    assert found is False
    assert ticket_id is None


def test_verify_evidence_quote_accepts_real_quote():
    tickets = [{"ticket_id": "t1", "body": "The dashboard is slow."}]
    found, ticket_id = verify_evidence_quote("the dashboard is slow", tickets)
    assert found is True
    assert ticket_id == "t1"


# ---------------------------------------------------------------------------
# Test 6 — sanitize removes unverified flags
# ---------------------------------------------------------------------------


def test_sanitize_risk_flags_removes_unverified():
    tickets = [
        {"ticket_id": "t1", "body": "If this is not fixed before renewal, we may cancel."}
    ]
    flags = [
        {
            "risk_type": "churn_risk",
            "severity": "high",
            "summary": "Churn risk",
            "evidence_quote": "we may cancel",
        },
        {
            "risk_type": "churn_risk",
            "severity": "high",
            "summary": "Fabricated",
            "evidence_quote": "we will cancel tomorrow",
        },
    ]
    sanitized = sanitize_risk_flags(flags, tickets)
    assert len(sanitized) == 1
    assert sanitized[0]["evidence_quote"] == "we may cancel"
    assert sanitized[0]["ticket_id"] == "t1"


# ---------------------------------------------------------------------------
# Test 7 — fallback returns valid response
# ---------------------------------------------------------------------------


def _patch_summarizer_data(monkeypatch, summarizer, accounts, tickets):
    monkeypatch.setattr(summarizer, "_load_accounts", lambda: accounts)
    monkeypatch.setattr(summarizer, "_load_tickets", lambda: tickets)


def test_generate_brief_fallback_when_llm_missing(monkeypatch):
    accounts = [{"account_id": "acct_1", "name": "Test Account"}]
    tickets = [
        {
            "ticket_id": "t1",
            "account_id": "acct_1",
            "created_at": "2026-06-18",
            "body": "If this is not fixed before renewal, we may cancel.",
        }
    ]

    class _NoKeyClient(LLMClient):
        def __init__(self):
            super().__init__(api_key="")

        def is_configured(self) -> bool:
            return False

        def complete_json(self, *args, **kwargs):
            raise MissingLLMConfigurationError("no key")

    summarizer = AccountHealthSummarizer(llm_client=_NoKeyClient())
    _patch_summarizer_data(monkeypatch, summarizer, accounts, tickets)

    brief = summarizer.generate_brief("acct_1")
    assert isinstance(brief, AccountBriefResponse)
    assert brief.account_id == "acct_1"
    assert brief.deterministic is True
    assert brief.ticket_count_used == 1
    assert len(brief.recommended_talking_points) >= 1
    # The churn signal has a verifiable quote, so exactly one risk flag survives.
    assert len(brief.open_risks_and_flagged_issues) == 1
    assert brief.open_risks_and_flagged_issues[0].evidence_quote


# ---------------------------------------------------------------------------
# Test 8 — LLM response post-processing removes invented quote
# ---------------------------------------------------------------------------


def test_generate_brief_drops_invented_llm_quote(monkeypatch):
    accounts = [{"account_id": "acct_1", "name": "Test Account"}]
    tickets = [
        {
            "ticket_id": "t1",
            "account_id": "acct_1",
            "created_at": "2026-06-18",
            "body": "If this is not fixed before renewal, we may cancel.",
        }
    ]

    raw_llm_output = {
        "account_id": "acct_1",
        "executive_summary": "One. Two. Three.",
        "open_risks_and_flagged_issues": [
            {
                "risk_type": "churn_risk",
                "severity": "high",
                "summary": "Real risk",
                "evidence_quote": "we may cancel",
                "ticket_id": "t1",
            },
            {
                "risk_type": "escalation",
                "severity": "high",
                "summary": "Invented risk",
                "evidence_quote": "we are suing you next week",
                "ticket_id": "t1",
            },
        ],
        "recommended_talking_points": ["Discuss renewal."],
        "prompt_version": "account_summary_v1",
    }

    class _FakeClient(LLMClient):
        def __init__(self):
            super().__init__(api_key="fake-key")

        def is_configured(self) -> bool:
            return True

        def complete_json(self, *args, **kwargs):
            return dict(raw_llm_output)

    summarizer = AccountHealthSummarizer(llm_client=_FakeClient())
    _patch_summarizer_data(monkeypatch, summarizer, accounts, tickets)

    brief = summarizer.generate_brief("acct_1")
    assert isinstance(brief, AccountBriefResponse)
    quotes = [flag.evidence_quote for flag in brief.open_risks_and_flagged_issues]
    assert "we may cancel" in quotes
    assert "we are suing you next week" not in quotes
    assert len(brief.open_risks_and_flagged_issues) == 1


# ---------------------------------------------------------------------------
# Extra — post-processing forces account_id and adds talking points
# ---------------------------------------------------------------------------


def test_post_process_forces_account_id_and_talking_points():
    tickets = [{"ticket_id": "t1", "body": "we may cancel"}]
    raw = {
        "account_id": "WRONG",
        "executive_summary": "",
        "open_risks_and_flagged_issues": "not-a-list",
        "recommended_talking_points": [],
    }
    processed = post_process_brief_response(raw, "acct_9", tickets, "account_summary_v1")
    assert processed["account_id"] == "acct_9"
    assert isinstance(processed["open_risks_and_flagged_issues"], list)
    assert len(processed["recommended_talking_points"]) >= 1
    assert processed["executive_summary"].strip()
    assert processed["ticket_count_used"] == 1
