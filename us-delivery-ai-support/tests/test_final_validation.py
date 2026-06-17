"""Tests for the final submission-validation tooling."""

from __future__ import annotations

from pathlib import Path

from scripts.final_validate import (
    CheckResult,
    FAIL,
    PASS,
    WARN,
    add_fail,
    add_pass,
    add_warn,
    has_failures,
    write_final_validation_report,
)


def test_module_imports():
    import scripts.final_validate as fv

    assert hasattr(fv, "run_validation")
    assert hasattr(fv, "write_final_validation_report")


def test_write_report_creates_markdown(tmp_path: Path):
    results: list[CheckResult] = []
    add_pass(results, "README exists", "README.md")
    add_warn(results, "Dataset readiness", "Official dataset not ready")
    out = tmp_path / "FINAL_VALIDATION.md"
    write_final_validation_report(results, out, generated_at="2026-06-19T00:00:00Z")

    text = out.read_text(encoding="utf-8")
    assert "# Final Validation Report" in text
    assert "| Status | Check | Details |" in text
    assert "README exists" in text
    assert "PASS" in text and "WARN" in text


def test_has_failures_true_when_fail_present():
    results = [CheckResult(PASS, "a", ""), CheckResult(FAIL, "b", "")]
    assert has_failures(results) is True


def test_has_failures_false_for_pass_and_warn_only():
    results = [CheckResult(PASS, "a", ""), CheckResult(WARN, "b", "")]
    assert has_failures(results) is False


def test_report_escapes_pipes(tmp_path: Path):
    results: list[CheckResult] = []
    add_fail(results, "weird | check", "details | with | pipes")
    out = tmp_path / "report.md"
    write_final_validation_report(results, out)
    text = out.read_text(encoding="utf-8")
    assert "weird \\| check" in text
