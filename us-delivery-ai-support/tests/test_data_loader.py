"""Tests for app.data_loader — official dataset loading with missing-data safety."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.config import Settings
from app.data_loader import (
    EmptyDatasetError,
    InvalidDatasetError,
    MissingDatasetError,
    check_dataset_status,
    filter_last_n_days_tickets,
    filter_tickets_for_account,
    load_json_file,
    normalize_records,
)


# ---------------------------------------------------------------------------
# load_json_file
# ---------------------------------------------------------------------------


def test_missing_json_file_raises(tmp_path: Path):
    with pytest.raises(MissingDatasetError):
        load_json_file(tmp_path / "missing.json", "tickets")


def test_empty_json_file_raises(tmp_path: Path):
    path = tmp_path / "tickets.json"
    path.write_text("", encoding="utf-8")
    with pytest.raises(EmptyDatasetError):
        load_json_file(path, "tickets")


def test_invalid_json_file_raises(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text("{not valid json}", encoding="utf-8")
    with pytest.raises(InvalidDatasetError):
        load_json_file(path, "tickets")


def test_valid_json_loads(tmp_path: Path):
    path = tmp_path / "valid.json"
    path.write_text('[{"id": "t1"}]', encoding="utf-8")
    result = load_json_file(path, "tickets")
    assert result == [{"id": "t1"}]


# ---------------------------------------------------------------------------
# normalize_records
# ---------------------------------------------------------------------------


def test_normalize_top_level_list():
    records = normalize_records([{"id": "1"}], ("tickets",), "tickets")
    assert records == [{"id": "1"}]


def test_normalize_dict_container():
    records = normalize_records({"tickets": [{"id": "1"}]}, ("tickets",), "tickets")
    assert records == [{"id": "1"}]


def test_normalize_empty_list_raises():
    with pytest.raises(EmptyDatasetError):
        normalize_records([], ("tickets",), "tickets")


def test_normalize_non_dict_record_raises():
    with pytest.raises(InvalidDatasetError):
        normalize_records(["not-a-dict"], ("tickets",), "tickets")


def test_normalize_unsupported_shape_raises():
    with pytest.raises(InvalidDatasetError):
        normalize_records(42, ("tickets",), "tickets")


def test_normalize_dict_without_known_key_raises():
    with pytest.raises(InvalidDatasetError):
        normalize_records({"unknown_key": [{"id": "1"}]}, ("tickets",), "tickets")


# ---------------------------------------------------------------------------
# filter_tickets_for_account
# ---------------------------------------------------------------------------


def test_filter_tickets_for_account():
    tickets = [
        {"id": "t1", "account_id": "acct_1"},
        {"id": "t2", "account_id": "acct_2"},
    ]
    result = filter_tickets_for_account(tickets, "acct_1")
    assert result == [{"id": "t1", "account_id": "acct_1"}]


def test_filter_tickets_for_account_no_match():
    tickets = [
        {"id": "t1", "account_id": "acct_1"},
    ]
    assert filter_tickets_for_account(tickets, "acct_999") == []


def test_filter_tickets_missing_account_field():
    """Tickets without account fields should be skipped, not crash."""
    tickets = [
        {"id": "t1"},
        {"id": "t2", "account_id": "acct_1"},
    ]
    assert filter_tickets_for_account(tickets, "acct_1") == [
        {"id": "t2", "account_id": "acct_1"}
    ]


# ---------------------------------------------------------------------------
# filter_last_n_days_tickets
# ---------------------------------------------------------------------------


def test_filter_last_n_days_excludes_old():
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    old = (now - timedelta(days=200)).strftime("%Y-%m-%dT%H:%M:%SZ")
    tickets = [
        {"id": "t1", "created_at": recent},
        {"id": "t2", "created_at": old},
    ]
    result = filter_last_n_days_tickets(tickets, days=90)
    assert len(result) == 1
    assert result[0]["id"] == "t1"


def test_filter_last_n_days_unparseable_date_skipped():
    tickets = [
        {"id": "t1", "created_at": "not-a-date"},
    ]
    assert filter_last_n_days_tickets(tickets, days=90) == []


# ---------------------------------------------------------------------------
# check_dataset_status
# ---------------------------------------------------------------------------


def test_check_dataset_status_not_ready(tmp_path: Path):
    settings = Settings(
        TICKETS_FILE=tmp_path / "tickets.json",
        ACCOUNTS_FILE=tmp_path / "accounts.json",
        KB_DIR=tmp_path / "kb",
    )
    status = check_dataset_status(settings)
    assert status.ready is False
    assert len(status.missing_or_empty) > 0


def test_check_dataset_status_ready(tmp_path: Path):
    # Create non-empty tickets and accounts
    tickets_file = tmp_path / "tickets.json"
    accounts_file = tmp_path / "accounts.json"
    tickets_file.write_text('[{"id": "t1"}]', encoding="utf-8")
    accounts_file.write_text('[{"id": "a1"}]', encoding="utf-8")

    # Create KB with a non-empty markdown file
    kb_dir = tmp_path / "kb"
    (kb_dir / "docs").mkdir(parents=True)
    (kb_dir / "docs" / "test.md").write_text("# Test\nContent.", encoding="utf-8")

    settings = Settings(
        TICKETS_FILE=tickets_file,
        ACCOUNTS_FILE=accounts_file,
        KB_DIR=kb_dir,
    )
    status = check_dataset_status(settings)
    assert status.ready is True
    assert status.kb_docs_count >= 1
