"""Official dataset loading utilities with missing-data safety."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.schemas import DatasetStatus


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TICKET_CONTAINER_KEYS = ("tickets", "data", "records", "items")
ACCOUNT_CONTAINER_KEYS = ("accounts", "customers", "data", "records", "items")
ACCOUNT_ID_FIELDS = ("account_id", "id", "customer_id", "accountId", "customerId")
TICKET_ACCOUNT_FIELDS = ("account_id", "customer_id", "accountId", "customerId")
DATE_FIELDS = (
    "created_at",
    "createdAt",
    "date",
    "timestamp",
    "updated_at",
    "updatedAt",
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DatasetError(Exception):
    """Base exception for official dataset problems."""


class MissingDatasetError(DatasetError):
    """Raised when required official dataset files are missing."""


class EmptyDatasetError(DatasetError):
    """Raised when required official dataset files are empty."""


class InvalidDatasetError(DatasetError):
    """Raised when required official dataset files are invalid JSON or unsupported shape."""


class RecordNotFoundError(DatasetError):
    """Raised when a requested official dataset record is not found."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _path_exists(path: Path) -> bool:
    """Check whether *path* exists and is a regular file."""
    return path.exists() and path.is_file()


def _path_non_empty(path: Path) -> bool:
    """Check whether *path* exists, is a regular file, and has >0 bytes."""
    return _path_exists(path) and path.stat().st_size > 0


def _try_parse_datetime(value: str) -> datetime | None:
    """Attempt to parse an ISO-like datetime string.

    Returns ``None`` instead of raising on unparseable values.
    """
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except (ValueError, TypeError):
            continue
    return None


# ---------------------------------------------------------------------------
# Core loaders
# ---------------------------------------------------------------------------


def load_json_file(path: Path, label: str) -> Any:
    """Load a required official JSON dataset file.

    Args:
        path: File path.
        label: Human-readable label like "tickets" or "accounts".

    Raises:
        MissingDatasetError: file does not exist.
        EmptyDatasetError: file exists but is zero bytes.
        InvalidDatasetError: invalid JSON.
    """
    if not path.exists() or not path.is_file():
        raise MissingDatasetError(
            f"Official {label} dataset file not found: {path}"
        )

    if path.stat().st_size == 0:
        raise EmptyDatasetError(
            f"Official {label} dataset file is empty (zero bytes): {path}"
        )

    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        raise InvalidDatasetError(
            f"Official {label} dataset file contains invalid JSON: {path} — {exc}"
        ) from exc


def normalize_records(
    raw: Any,
    possible_keys: tuple[str, ...],
    label: str,
) -> list[dict[str, Any]]:
    """Normalize supported dataset shapes into a list of dictionaries.

    Supported shapes:
        1. Top-level list of dicts.
        2. Top-level dict with a known container key holding a list.

    Raises:
        EmptyDatasetError: if the resolved list is empty.
        InvalidDatasetError: if the shape is unsupported or items are not dicts.
    """
    records: list[Any] | None = None

    if isinstance(raw, list):
        records = raw
    elif isinstance(raw, dict):
        for key in possible_keys:
            if key in raw and isinstance(raw[key], list):
                records = raw[key]
                break
        if records is None:
            raise InvalidDatasetError(
                f"Unsupported {label} dataset shape: expected a top-level list or "
                f"a dict with one of {possible_keys} containing a list."
            )
    else:
        raise InvalidDatasetError(
            f"Unsupported {label} dataset shape: expected list or dict, "
            f"got {type(raw).__name__}."
        )

    if not records:
        raise EmptyDatasetError(f"{label} dataset contains zero records.")

    for idx, item in enumerate(records):
        if not isinstance(item, dict):
            raise InvalidDatasetError(
                f"{label} dataset record #{idx} is not a dict: {type(item).__name__}."
            )

    return records


# ---------------------------------------------------------------------------
# Public loader functions
# ---------------------------------------------------------------------------


def load_tickets(settings: Settings | None = None) -> list[dict[str, Any]]:
    """Load official support tickets."""
    if settings is None:
        settings = get_settings()
    raw = load_json_file(settings.tickets_file, "tickets")
    return normalize_records(raw, TICKET_CONTAINER_KEYS, "tickets")


def load_accounts(settings: Settings | None = None) -> list[dict[str, Any]]:
    """Load official customer account summaries."""
    if settings is None:
        settings = get_settings()
    raw = load_json_file(settings.accounts_file, "accounts")
    return normalize_records(raw, ACCOUNT_CONTAINER_KEYS, "accounts")


def load_account_by_id(
    account_id: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Find an account by a flexible ID field.

    Supports fields: account_id, id, customer_id, accountId, customerId.

    Raises:
        RecordNotFoundError: if no account matches the given ID.
    """
    accounts = load_accounts(settings)
    for account in accounts:
        for field in ACCOUNT_ID_FIELDS:
            if str(account.get(field, "")).strip() == account_id.strip():
                return account
    raise RecordNotFoundError(
        f"Account with ID '{account_id}' not found in official dataset."
    )


def filter_tickets_for_account(
    tickets: list[dict[str, Any]],
    account_id: str,
) -> list[dict[str, Any]]:
    """Return tickets linked to the given account ID using flexible account fields."""
    matched: list[dict[str, Any]] = []
    for ticket in tickets:
        for field in TICKET_ACCOUNT_FIELDS:
            if str(ticket.get(field, "")).strip() == account_id.strip():
                matched.append(ticket)
                break
    return matched


def filter_last_n_days_tickets(
    tickets: list[dict[str, Any]],
    days: int = 90,
) -> list[dict[str, Any]]:
    """Filter tickets to the last *days* days using flexible date fields.

    Tickets whose date cannot be parsed are silently skipped.
    Results are returned in descending order (most recent first).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    dated: list[tuple[datetime, dict[str, Any]]] = []

    for ticket in tickets:
        parsed: datetime | None = None
        for field in DATE_FIELDS:
            raw_value = ticket.get(field)
            if raw_value is not None and isinstance(raw_value, str):
                parsed = _try_parse_datetime(raw_value)
                if parsed is not None:
                    break

        if parsed is None:
            continue

        # Ensure timezone-aware comparison
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        if parsed >= cutoff:
            dated.append((parsed, ticket))

    # Sort descending — most recent first
    dated.sort(key=lambda pair: pair[0], reverse=True)
    return [ticket for _, ticket in dated]


# ---------------------------------------------------------------------------
# Dataset status
# ---------------------------------------------------------------------------


def check_dataset_status(settings: Settings | None = None) -> DatasetStatus:
    """Return readiness of official JSON datasets and KB folder."""
    if settings is None:
        settings = get_settings()

    tickets_exists = _path_exists(settings.tickets_file)
    tickets_non_empty = _path_non_empty(settings.tickets_file)
    accounts_exists = _path_exists(settings.accounts_file)
    accounts_non_empty = _path_non_empty(settings.accounts_file)

    kb_exists = settings.kb_dir.exists() and settings.kb_dir.is_dir()
    kb_docs_count = 0
    if kb_exists:
        kb_docs_count = sum(
            1
            for p in settings.kb_dir.rglob("*.md")
            if not any(part.startswith(".") for part in p.parts)
            and p.stat().st_size > 0
        )

    missing_or_empty: list[str] = []
    if not tickets_exists or not tickets_non_empty:
        missing_or_empty.append(str(settings.tickets_file))
    if not accounts_exists or not accounts_non_empty:
        missing_or_empty.append(str(settings.accounts_file))
    if not kb_exists or kb_docs_count == 0:
        missing_or_empty.append("knowledge-base/**/*.md")

    ready = (
        tickets_exists
        and tickets_non_empty
        and accounts_exists
        and accounts_non_empty
        and kb_exists
        and kb_docs_count > 0
    )

    message = "All official datasets are ready." if ready else (
        "Official dataset is incomplete. Missing or empty: "
        + ", ".join(missing_or_empty)
    )

    return DatasetStatus(
        tickets_file_exists=tickets_exists,
        tickets_file_non_empty=tickets_non_empty,
        accounts_file_exists=accounts_exists,
        accounts_file_non_empty=accounts_non_empty,
        kb_dir_exists=kb_exists,
        kb_docs_count=kb_docs_count,
        ready=ready,
        message=message,
        missing_or_empty=missing_or_empty,
    )
