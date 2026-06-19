"""Tests for the Task 3 eval runner and report generation.

Uses temp files and fakes. No official dataset and no real LLM key required.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.schemas import (
    AccountBriefResponse,
    EvalCaseResult,
    EvalReport,
    KnownIssueMatch,
    TicketTriageResponse,
)
from evals.report import write_json_report, write_markdown_report
from evals.run_evals import (
    EvalRunnerError,
    build_eval_report,
    load_eval_cases,
    run_account_case,
    run_all_evals,
    run_triage_case,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeTriageAgent:
    def triage(self, request) -> TicketTriageResponse:
        return TicketTriageResponse(
            product_area="Authentication/SSO",
            issue_category="login",
            urgency_tier="P1",
            reasoning="All users blocked by an SSO outage.",
            known_issue_match=KnownIssueMatch(matched=False),
            recommended_team="Authentication/SSO",
            draft_first_response="We are investigating the SSO outage now.",
            prompt_version="triage_v1",
        )


class _FakeSummarizer:
    def generate_brief(self, account_id: str) -> AccountBriefResponse:
        return AccountBriefResponse(
            account_id=account_id,
            executive_summary="One. Two. Three.",
            open_risks_and_flagged_issues=[],
            recommended_talking_points=["Review recent tickets."],
            ticket_count_used=0,
            prompt_version="account_summary_v1",
        )


def _triage_case() -> dict:
    return {
        "id": "triage_001",
        "name": "SSO outage",
        "task": "triage",
        "input": {"subject": "SSO outage", "body": "All users cannot log in."},
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


# Test 1 — load_eval_cases loads valid list
def test_load_eval_cases_loads_list(tmp_path: Path):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([_triage_case()]), encoding="utf-8")
    cases = load_eval_cases(path)
    assert isinstance(cases, list)
    assert len(cases) == 1


# Test 2 — load_eval_cases rejects non-list JSON
def test_load_eval_cases_rejects_non_list(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    with pytest.raises(EvalRunnerError):
        load_eval_cases(path)


def test_load_eval_cases_missing_file(tmp_path: Path):
    with pytest.raises(EvalRunnerError):
        load_eval_cases(tmp_path / "does_not_exist.json")


# Test 3 — run_triage_case returns EvalCaseResult
def test_run_triage_case_returns_result():
    result = run_triage_case(_triage_case(), _FakeTriageAgent())
    assert isinstance(result, EvalCaseResult)
    assert result.id == "triage_001"
    assert 0.0 <= result.score <= 1.0
    assert result.passed is True


# Test 4 — account case fails gracefully when dataset missing
def test_account_case_fails_gracefully_when_dataset_missing():
    case = {
        "id": "account_001",
        "name": "Account brief",
        "task": "account_summary",
        "input": {"account_id": "PLACEHOLDER_ACCOUNT_ID"},
        "acceptance_criteria": {},
        "adversarial": False,
        "requires_official_dataset": True,
    }
    result = run_account_case(case, _FakeSummarizer(), dataset_ready=False)
    assert result.passed is False
    assert result.score == 0.0
    assert any("dataset" in note.lower() for note in result.notes)


# Test 5 — JSON report writes valid file
def test_write_json_report(tmp_path: Path):
    report = build_eval_report(
        [run_triage_case(_triage_case(), _FakeTriageAgent())], dataset_ready=False
    )
    path = tmp_path / "report.json"
    write_json_report(report, path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["total_cases"] == 1
    assert "results" in data
    assert data["dataset_ready"] is False


# Test 6 — Markdown report writes table
def test_write_markdown_report(tmp_path: Path):
    report = build_eval_report(
        [run_triage_case(_triage_case(), _FakeTriageAgent())], dataset_ready=False
    )
    path = tmp_path / "report.md"
    write_markdown_report(report, path)
    text = path.read_text(encoding="utf-8")
    assert "# Evaluation Report" in text
    assert "| ID | Task | Name |" in text


# Test 7 — run_all_evals writes both reports
def test_run_all_evals_writes_reports(tmp_path: Path, monkeypatch):
    triage_path = tmp_path / "triage.json"
    account_path = tmp_path / "account.json"
    triage_path.write_text(json.dumps([_triage_case()]), encoding="utf-8")
    account_path.write_text(
        json.dumps(
            [
                {
                    "id": "account_001",
                    "name": "Account brief",
                    "task": "account_summary",
                    "input": {"account_id": "PLACEHOLDER"},
                    "acceptance_criteria": {},
                    "adversarial": False,
                    "requires_official_dataset": True,
                }
            ]
        ),
        encoding="utf-8",
    )

    import evals.run_evals as run_evals

    monkeypatch.setattr(run_evals, "TicketTriageAgent", lambda *a, **k: _FakeTriageAgent())
    monkeypatch.setattr(run_evals, "AccountHealthSummarizer", lambda *a, **k: _FakeSummarizer())

    json_out = tmp_path / "eval_report.json"
    md_out = tmp_path / "eval_report.md"
    report = run_all_evals(
        triage_cases_path=triage_path,
        account_cases_path=account_path,
        output_json_path=json_out,
        output_md_path=md_out,
    )
    assert json_out.exists()
    assert md_out.exists()
    assert report.total_cases == 2


# Test 8 — default case/report paths are absolute (CWD-independent)
def test_default_paths_are_absolute_and_exist():
    import evals.run_evals as run_evals

    assert run_evals.DEFAULT_TRIAGE_PATH.is_absolute()
    assert run_evals.DEFAULT_TRIAGE_PATH.exists()
    assert run_evals.DEFAULT_ACCOUNT_PATH.is_absolute()
    assert run_evals.DEFAULT_ACCOUNT_PATH.exists()
    assert Path(run_evals.DEFAULT_JSON_REPORT).is_absolute()
    assert Path(run_evals.DEFAULT_MD_REPORT).is_absolute()


# Test 9 — run_all_evals works when launched from an unrelated CWD (the bug the
# Streamlit "Run evals" button hit: it launches from the repository root).
def test_run_all_evals_works_from_unrelated_cwd(tmp_path: Path, monkeypatch):
    import evals.run_evals as run_evals

    monkeypatch.setattr(run_evals, "TicketTriageAgent", lambda *a, **k: _FakeTriageAgent())
    monkeypatch.setattr(
        run_evals, "AccountHealthSummarizer", lambda *a, **k: _FakeSummarizer()
    )
    monkeypatch.chdir(tmp_path)

    json_out = tmp_path / "out.json"
    md_out = tmp_path / "out.md"
    # No case paths passed -> must resolve the absolute default case files even
    # though the working directory is unrelated to the project.
    report = run_all_evals(output_json_path=json_out, output_md_path=md_out)
    assert json_out.exists()
    assert md_out.exists()
    assert report.total_cases >= 10
