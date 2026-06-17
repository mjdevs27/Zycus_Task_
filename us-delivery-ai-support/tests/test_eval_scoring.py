"""Tests for the Task 3 scoring engine. No LLM or official data required."""

from __future__ import annotations

from evals.scoring import (
    clamp_score,
    count_sentences,
    score_account_summary_case,
    score_case,
    score_triage_case,
)


def _valid_triage_output() -> dict:
    return {
        "product_area": "Authentication/SSO",
        "issue_category": "login",
        "urgency_tier": "P1",
        "reasoning": "All users are blocked after a SAML change, indicating an outage.",
        "known_issue_match": {"matched": False},
        "recommended_team": "Authentication/SSO",
        "draft_first_response": "We are investigating the SSO outage and will update you.",
        "retrieved_docs": [],
    }


def _triage_case() -> dict:
    return {
        "id": "triage_001",
        "name": "SSO outage",
        "task": "triage",
        "acceptance_criteria": {
            "required_fields": [
                "product_area",
                "issue_category",
                "urgency_tier",
                "reasoning",
                "known_issue_match",
                "recommended_team",
                "draft_first_response",
            ],
            "allowed_urgency": ["P1", "P2"],
            "must_include_reasoning": True,
            "must_include_draft_response": True,
        },
        "adversarial": False,
    }


def _valid_account_output() -> dict:
    return {
        "account_id": "acct_1",
        "executive_summary": "One sentence. Two sentence. Three sentence.",
        "open_risks_and_flagged_issues": [
            {
                "risk_type": "churn_risk",
                "severity": "high",
                "summary": "Renewal at risk.",
                "evidence_quote": "we may cancel",
                "ticket_id": "t1",
            }
        ],
        "recommended_talking_points": ["Discuss renewal."],
        "ticket_count_used": 1,
        "prompt_version": "account_summary_v1",
    }


def _account_case() -> dict:
    return {
        "id": "account_001",
        "name": "Account brief",
        "task": "account_summary",
        "acceptance_criteria": {
            "required_fields": [
                "account_id",
                "executive_summary",
                "open_risks_and_flagged_issues",
                "recommended_talking_points",
            ],
            "executive_summary_sentence_range": [3, 5],
            "requires_direct_ticket_quote_for_each_risk": True,
            "minimum_talking_points": 1,
        },
        "adversarial": False,
    }


# Test 1 — valid triage output passes
def test_valid_triage_passes():
    score, passed, _notes = score_triage_case(_triage_case(), _valid_triage_output())
    assert passed is True
    assert score >= 0.7


# Test 2 — invalid urgency penalized
def test_invalid_urgency_penalized():
    output = _valid_triage_output()
    output["urgency_tier"] = "Critical"
    score, _passed, notes = score_triage_case(_triage_case(), output)
    assert score < 1.0
    assert any("invalid" in note.lower() for note in notes)


# Test 3 — missing required field penalized
def test_missing_required_field_penalized():
    output = _valid_triage_output()
    del output["recommended_team"]
    score, _passed, notes = score_triage_case(_triage_case(), output)
    full, _p, _n = score_triage_case(_triage_case(), _valid_triage_output())
    assert score < full
    assert any("recommended_team" in note for note in notes)


# Test 4 — hallucinated KB doc path penalized
def test_hallucinated_doc_path_penalized():
    output = _valid_triage_output()
    output["known_issue_match"] = {
        "matched": True,
        "doc_title": "Fake",
        "doc_path": "fake.md",
        "match_reason": "made up",
    }
    output["retrieved_docs"] = [{"path": "real.md", "title": "Real"}]
    score, _passed, notes = score_triage_case(_triage_case(), output)
    assert any("fake.md" in note for note in notes)


# Test 5 — valid account summary passes
def test_valid_account_summary_passes():
    source_tickets = [{"ticket_id": "t1", "body": "we may cancel before renewal"}]
    score, passed, _notes = score_account_summary_case(
        _account_case(), _valid_account_output(), source_tickets
    )
    assert passed is True
    assert score >= 0.7


# Test 6 — account risk quote not found penalized
def test_account_risk_quote_not_found_penalized():
    source_tickets = [{"ticket_id": "t1", "body": "the dashboard is slow"}]
    score, _passed, notes = score_account_summary_case(
        _account_case(), _valid_account_output(), source_tickets
    )
    assert score < 1.0
    assert any("not found" in note.lower() for note in notes)


# Test 7 — sentence count penalty
def test_sentence_count_penalty():
    output = _valid_account_output()
    output["executive_summary"] = "Only one sentence here."
    score, _passed, notes = score_account_summary_case(
        _account_case(), output, [{"body": "we may cancel"}]
    )
    assert any("sentence" in note.lower() for note in notes)


# Test 8 — empty talking points penalty
def test_empty_talking_points_penalty():
    output = _valid_account_output()
    output["recommended_talking_points"] = []
    score, _passed, notes = score_account_summary_case(
        _account_case(), output, [{"body": "we may cancel"}]
    )
    assert score < 1.0
    assert any("talking point" in note.lower() for note in notes)


# Test 9 — clamp score works
def test_clamp_score():
    assert clamp_score(-1) == 0.0
    assert clamp_score(2) == 1.0
    assert clamp_score(0.123456) == 0.123


def test_count_sentences():
    assert count_sentences("One. Two. Three.") == 3
    assert count_sentences("Only one") == 1


def test_score_case_returns_eval_result():
    result = score_case(_triage_case(), _valid_triage_output())
    assert result.id == "triage_001"
    assert 0.0 <= result.score <= 1.0
    assert result.passed is True
