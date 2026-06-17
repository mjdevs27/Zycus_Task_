"""Task 3 — evaluation runner.

Runs Task 1 (triage) and Task 2 (account-summary) eval cases, scores each with
:mod:`evals.scoring`, and writes JSON + Markdown reports. The runner never
crashes when the official dataset is missing: triage cases run through the
deterministic local fallback, and account-summary cases that require official
data fail gracefully with score 0 and an explanatory note.

CLI:
    python -m evals.run_evals
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.account_summarizer import AccountHealthSummarizer
from app.data_loader import check_dataset_status
from app.schemas import EvalCaseResult, EvalReport, TicketTriageRequest
from app.triage_agent import TicketTriageAgent
from evals.report import write_json_report, write_markdown_report
from evals.scoring import score_case

logger = logging.getLogger("evals.run_evals")

DEFAULT_TRIAGE_PATH = "evals/test_cases/triage_tests.json"
DEFAULT_ACCOUNT_PATH = "evals/test_cases/account_summary_tests.json"
DEFAULT_JSON_REPORT = "eval_report.json"
DEFAULT_MD_REPORT = "eval_report.md"


class EvalRunnerError(Exception):
    """Raised for invalid case files or runner-level problems."""


def load_eval_cases(path: str | Path) -> list[dict]:
    """Load a list of eval cases from a JSON file."""
    path = Path(path)
    if not path.exists():
        raise EvalRunnerError(f"Eval case file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EvalRunnerError(f"Eval case file is not valid JSON: {path} — {exc}") from exc
    if not isinstance(data, list):
        raise EvalRunnerError(
            f"Eval case file must contain a top-level JSON list: {path}"
        )
    return data


def _failed_result(case: dict, notes: list[str]) -> EvalCaseResult:
    task = case.get("task")
    safe_task = task if task in ("triage", "account_summary") else "triage"
    return EvalCaseResult(
        id=case.get("id", "unknown"),
        name=case.get("name", "unknown"),
        task=safe_task,
        passed=False,
        score=0.0,
        notes=notes,
        adversarial=bool(case.get("adversarial", False)),
    )


def run_triage_case(case: dict, agent: TicketTriageAgent) -> EvalCaseResult:
    """Run and score one triage case. Never crashes the whole runner."""
    try:
        request = TicketTriageRequest(**(case.get("input") or {}))
        output = agent.triage(request)
        return score_case(case, output)
    except Exception as exc:  # noqa: BLE001 - isolate one bad case
        logger.info("Triage case %s failed: %s", case.get("id"), exc)
        return _failed_result(
            case, [f"Triage case error: {type(exc).__name__}: {exc}"]
        )


def run_account_case(
    case: dict,
    summarizer: AccountHealthSummarizer,
    dataset_ready: bool,
) -> EvalCaseResult:
    """Run and score one account-summary case. Never crashes the whole runner."""
    requires_dataset = bool(case.get("requires_official_dataset"))
    if requires_dataset and not dataset_ready:
        return _failed_result(
            case,
            [
                "Official dataset is not ready, so this account-summary case "
                "could not be executed without inventing account data."
            ],
        )
    try:
        account_id = (case.get("input") or {}).get("account_id", "")
        output = summarizer.generate_brief(account_id)
        return score_case(case, output)
    except Exception as exc:  # noqa: BLE001 - isolate one bad case
        logger.info("Account case %s failed: %s", case.get("id"), exc)
        return _failed_result(
            case, [f"Account case error: {type(exc).__name__}: {exc}"]
        )


def build_eval_report(
    results: list[EvalCaseResult],
    dataset_ready: bool,
) -> EvalReport:
    """Aggregate scored results into an :class:`EvalReport`."""
    total = len(results)
    passed = sum(1 for result in results if result.passed)
    failed = total - passed
    average = round(sum(r.score for r in results) / total, 3) if total else 0.0
    return EvalReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_cases=total,
        passed_cases=passed,
        failed_cases=failed,
        average_score=average,
        results=results,
        dataset_ready=dataset_ready,
    )


def run_all_evals(
    triage_cases_path: str | Path = DEFAULT_TRIAGE_PATH,
    account_cases_path: str | Path = DEFAULT_ACCOUNT_PATH,
    output_json_path: str | Path = DEFAULT_JSON_REPORT,
    output_md_path: str | Path = DEFAULT_MD_REPORT,
) -> EvalReport:
    """Run all eval cases, write reports, and return the :class:`EvalReport`."""
    triage_cases = load_eval_cases(triage_cases_path)
    account_cases = load_eval_cases(account_cases_path)

    status = check_dataset_status()
    dataset_ready = status.ready

    agent = TicketTriageAgent()
    summarizer = AccountHealthSummarizer()

    results: list[EvalCaseResult] = []
    for case in triage_cases:
        results.append(run_triage_case(case, agent))
    for case in account_cases:
        results.append(run_account_case(case, summarizer, dataset_ready))

    report = build_eval_report(results, dataset_ready)
    write_json_report(report, output_json_path)
    write_markdown_report(report, output_md_path)
    return report


def main() -> None:
    """CLI entrypoint: run all evals and print a summary."""
    logging.basicConfig(level=logging.WARNING)
    report = run_all_evals()
    print("Evaluation complete.")
    print(f"Total cases: {report.total_cases}")
    print(f"Passed: {report.passed_cases}")
    print(f"Failed: {report.failed_cases}")
    print(f"Average score: {report.average_score}")
    print(f"Dataset ready: {str(report.dataset_ready).lower()}")
    print("Reports:")
    print(f"- {DEFAULT_JSON_REPORT}")
    print(f"- {DEFAULT_MD_REPORT}")


if __name__ == "__main__":
    main()
