"""Validation tests for the Task 3 evaluation case files.

These tests check the structure of the eval case files only. They do not call
the LLM and do not require the official dataset.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

TRIAGE_PATH = Path("evals/test_cases/triage_tests.json")
ACCOUNT_PATH = Path("evals/test_cases/account_summary_tests.json")

REQUIRED_KEYS = {"id", "name", "task", "input", "acceptance_criteria", "adversarial"}
PLACEHOLDER_MARKERS = ("PLACEHOLDER", "REPLACE", "MISSING", "OFFICIAL")


def _load(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def triage_cases() -> list[dict]:
    return _load(TRIAGE_PATH)


@pytest.fixture(scope="module")
def account_cases() -> list[dict]:
    return _load(ACCOUNT_PATH)


# Test 1 — triage file exists and has >= 5 cases
def test_triage_file_has_at_least_five_cases(triage_cases):
    assert isinstance(triage_cases, list)
    assert len(triage_cases) >= 5


# Test 2 — account file exists and has >= 5 cases
def test_account_file_has_at_least_five_cases(account_cases):
    assert isinstance(account_cases, list)
    assert len(account_cases) >= 5


# Test 3 — triage cases have required keys
def test_triage_cases_have_required_keys(triage_cases):
    for case in triage_cases:
        assert REQUIRED_KEYS.issubset(case.keys()), case.get("id")
        assert case["task"] == "triage"


# Test 4 — account cases have required keys
def test_account_cases_have_required_keys(account_cases):
    for case in account_cases:
        assert REQUIRED_KEYS.issubset(case.keys()), case.get("id")
        assert case["task"] == "account_summary"


# Test 5 — at least one adversarial triage case
def test_at_least_one_adversarial_triage_case(triage_cases):
    assert any(case.get("adversarial") for case in triage_cases)


# Test 6 — at least one adversarial account case
def test_at_least_one_adversarial_account_case(account_cases):
    assert any(case.get("adversarial") for case in account_cases)


# Test 7 — placeholder account IDs are clearly labelled
def test_placeholder_account_ids_are_labelled(account_cases):
    for case in account_cases:
        if case.get("requires_official_dataset"):
            account_id = str(case["input"].get("account_id", ""))
            assert any(marker in account_id.upper() for marker in PLACEHOLDER_MARKERS), (
                f"Case {case['id']} requires official dataset but its account_id "
                f"'{account_id}' is not clearly labelled as a placeholder."
            )


# Test 8 — files are valid JSON (loading via fixtures already proves this)
def test_files_are_valid_json():
    assert isinstance(_load(TRIAGE_PATH), list)
    assert isinstance(_load(ACCOUNT_PATH), list)
