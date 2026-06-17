"""Tests for Pydantic schemas and output contracts."""

import pytest
from pydantic import ValidationError

from app.schemas import (
    AccountBriefResponse,
    KnownIssueMatch,
    RiskFlag,
    TicketTriageRequest,
    TicketTriageResponse,
)


def test_ticket_triage_request_accepts_free_text():
    request = TicketTriageRequest(text="Users cannot log in.")
    assert "Users cannot log in" in request.combined_text


def test_ticket_triage_request_accepts_subject_body():
    request = TicketTriageRequest(subject="Login broken", body="SSO errors for users")
    assert "Subject: Login broken" in request.combined_text
    assert "Body: SSO errors for users" in request.combined_text


def test_ticket_triage_request_rejects_empty_input():
    with pytest.raises(ValidationError):
        TicketTriageRequest()


def test_known_issue_match_requires_doc_when_matched():
    with pytest.raises(ValidationError):
        KnownIssueMatch(matched=True)


def test_ticket_triage_response_validates_urgency():
    response = TicketTriageResponse(
        product_area="Authentication",
        issue_category="Login failure",
        urgency_tier="P2",
        reasoning="Multiple users are affected.",
        known_issue_match=KnownIssueMatch(matched=False),
        recommended_team="Support",
        draft_first_response="Thanks for reporting this. We are investigating.",
        prompt_version="triage_v1",
    )
    assert response.urgency_tier == "P2"


def test_ticket_triage_response_rejects_invalid_urgency():
    with pytest.raises(ValidationError):
        TicketTriageResponse(
            product_area="Authentication",
            issue_category="Login failure",
            urgency_tier="P5",
            reasoning="Invalid urgency should fail.",
            known_issue_match=KnownIssueMatch(matched=False),
            recommended_team="Support",
            draft_first_response="Response text.",
            prompt_version="triage_v1",
        )


def test_risk_flag_requires_quote():
    with pytest.raises(ValidationError):
        RiskFlag(
            risk_type="churn_risk",
            severity="high",
            summary="Customer may churn.",
            evidence_quote="",
        )


def test_account_brief_response_basic_contract():
    response = AccountBriefResponse(
        account_id="acct_test",
        executive_summary=(
            "The account has recurring support issues. "
            "The TAM should review risks. "
            "Next steps should be aligned before renewal."
        ),
        open_risks_and_flagged_issues=[],
        recommended_talking_points=["Review open tickets", "Align on renewal risks"],
        ticket_count_used=2,
        prompt_version="account_summary_v1",
    )
    assert response.account_id == "acct_test"
    assert response.deterministic is True
    assert response.ticket_count_used == 2
