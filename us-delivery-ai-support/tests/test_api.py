"""Tests for the FastAPI layer.

The app must start and serve ``/``, ``/health`` and ``/dataset/status`` without
any dataset or LLM key. Data-dependent routes are exercised with monkeypatched
agents so no real LLM or official data is required.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

import app.main as main
from app.account_summarizer import AccountNotFoundError
from app.schemas import (
    AccountBriefResponse,
    KnownIssueMatch,
    TicketTriageResponse,
)

client = TestClient(main.app)


def _sample_triage_response() -> TicketTriageResponse:
    return TicketTriageResponse(
        product_area="Authentication/SSO",
        issue_category="login",
        urgency_tier="P1",
        reasoning="All users blocked after SAML change.",
        known_issue_match=KnownIssueMatch(matched=False),
        recommended_team="Authentication/SSO",
        draft_first_response="We are investigating the SSO outage now.",
        prompt_version="triage_v1",
    )


def _sample_account_brief(account_id: str = "acct_1") -> AccountBriefResponse:
    return AccountBriefResponse(
        account_id=account_id,
        executive_summary="One. Two. Three.",
        open_risks_and_flagged_issues=[],
        recommended_talking_points=["Review recent tickets."],
        ticket_count_used=0,
        prompt_version="account_summary_v1",
    )


# ---------------------------------------------------------------------------
# Test 1 — root endpoint works
# ---------------------------------------------------------------------------


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "us-delivery-ai-support"


# ---------------------------------------------------------------------------
# Test 2 — health endpoint works
# ---------------------------------------------------------------------------


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Test 3 — dataset status endpoint works
# ---------------------------------------------------------------------------


def test_dataset_status_endpoint():
    response = client.get("/dataset/status")
    assert response.status_code == 200
    assert "ready" in response.json()


# ---------------------------------------------------------------------------
# Test 4 — triage endpoint accepts text
# ---------------------------------------------------------------------------


def test_triage_endpoint_accepts_text(monkeypatch):
    monkeypatch.setattr(
        main.TicketTriageAgent, "triage", lambda self, request: _sample_triage_response()
    )
    response = client.post("/triage", json={"text": "Users cannot log in via SSO."})
    assert response.status_code == 200
    assert response.json()["urgency_tier"] == "P1"


# ---------------------------------------------------------------------------
# Test 5 — triage endpoint accepts subject/body
# ---------------------------------------------------------------------------


def test_triage_endpoint_accepts_subject_body(monkeypatch):
    monkeypatch.setattr(
        main.TicketTriageAgent, "triage", lambda self, request: _sample_triage_response()
    )
    response = client.post(
        "/triage",
        json={"subject": "SSO login broken", "body": "Users get SAML errors."},
    )
    assert response.status_code == 200


def test_triage_endpoint_rejects_empty_request():
    response = client.post("/triage", json={})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Test 6 — account brief success
# ---------------------------------------------------------------------------


def test_account_brief_success(monkeypatch):
    monkeypatch.setattr(
        main.AccountHealthSummarizer,
        "generate_brief",
        lambda self, account_id: _sample_account_brief(account_id),
    )
    response = client.post("/accounts/acct_1/brief")
    assert response.status_code == 200
    assert response.json()["account_id"] == "acct_1"


# ---------------------------------------------------------------------------
# Test 7 — account not found
# ---------------------------------------------------------------------------


def test_account_not_found(monkeypatch):
    def _raise(self, account_id):
        raise AccountNotFoundError(f"Account not found: {account_id}")

    monkeypatch.setattr(main.AccountHealthSummarizer, "generate_brief", _raise)
    response = client.post("/accounts/missing/brief")
    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["type"] == "AccountNotFound"
    assert "missing" in detail["message"]


# ---------------------------------------------------------------------------
# Test 8 — eval route returns summary
# ---------------------------------------------------------------------------


def test_eval_route_returns_summary(monkeypatch):
    from app.schemas import EvalReport

    fake_report = EvalReport(
        generated_at="2026-06-18T00:00:00",
        total_cases=2,
        passed_cases=1,
        failed_cases=1,
        average_score=0.5,
        results=[],
        dataset_ready=False,
    )
    # Patch the symbol where it is imported inside the route.
    import evals.run_evals as run_evals

    monkeypatch.setattr(run_evals, "run_all_evals", lambda *a, **k: fake_report)
    response = client.post("/evals/run")
    assert response.status_code == 200
    body = response.json()
    assert "summary" in body
    assert body["summary"]["total_cases"] == 2
    assert body["summary"]["dataset_ready"] is False
