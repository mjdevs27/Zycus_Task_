"""Task 2 — TAM Account Health Summariser.

Generates a concise, deterministic account brief from official account data and
the account's ticket history (last 90 days). The module:

* loads official data lazily inside :meth:`AccountHealthSummarizer.generate_brief`
  (never at construction time, so API startup and ``/health`` keep working),
* detects churn / escalation risk quote candidates locally before any LLM call,
* redacts PII before prompt construction,
* verifies every risk evidence quote against actual ticket text, and
* degrades to a deterministic local fallback when no LLM is configured.

It never invents account or ticket data, and never lets an unverified
(hallucinated) evidence quote survive into the final brief.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError

from app.config import Settings, get_settings
from app.data_loader import (
    EmptyDatasetError,
    MissingDatasetError,
    load_accounts,
    load_tickets,
)
from app.llm_client import LLMClient, LLMClientError
from app.pii import redact_account_payload, redact_ticket_payload
from app.prompt_loader import (
    PromptError,
    get_prompt_version,
    load_prompt,
    render_prompt,
)
from app.schemas import AccountBriefResponse

logger = logging.getLogger("app.account_summarizer")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACCOUNT_ID_KEYS = ("account_id", "id", "customer_id", "accountId", "customerId")
TICKET_ACCOUNT_KEYS = (
    "account_id",
    "customer_id",
    "accountId",
    "customerId",
    "account",
    "customer",
)
TICKET_ID_KEYS = ("ticket_id", "id", "case_id", "ticketId")
DATE_KEYS = ("created_at", "createdAt", "created", "timestamp", "date", "updated_at")

TICKET_TEXT_FIELDS = (
    "subject",
    "title",
    "body",
    "description",
    "message",
    "comments",
    "status",
    "priority",
    "category",
)

# Ordered (term, signal) pairs for local risk detection. Order matters: the
# first matching term per ticket determines the candidate signal.
RISK_TERMS: tuple[tuple[str, str], ...] = (
    ("churn", "churn_risk"),
    ("cancellation", "churn_risk"),
    ("cancel", "churn_risk"),
    ("not renew", "churn_risk"),
    ("renewal", "churn_risk"),
    ("terminate", "churn_risk"),
    ("switch vendor", "churn_risk"),
    ("competitor", "churn_risk"),
    ("escalation", "escalation"),
    ("escalate", "escalation"),
    ("executive", "escalation"),
    ("unacceptable", "escalation"),
    ("breach", "escalation"),
    ("sla", "escalation"),
    ("urgent", "escalation"),
    ("production down", "unresolved_issue"),
    ("outage", "unresolved_issue"),
    ("all users", "unresolved_issue"),
    ("blocked", "unresolved_issue"),
)

_SEVERITY_FOR_SIGNAL = {
    "churn_risk": "high",
    "escalation": "high",
    "unresolved_issue": "medium",
    "other": "low",
}

_MAX_QUOTE_CHARS = 300

_DEFAULT_TALKING_POINT = "Confirm current open support priorities with the customer."


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class AccountSummaryError(Exception):
    """Base exception for account summarisation problems."""


class AccountNotFoundError(AccountSummaryError):
    """Raised when no account matches the requested ID."""


class AccountDataError(AccountSummaryError):
    """Raised for invalid input or unusable account data."""


class EvidenceQuoteError(AccountSummaryError):
    """Raised when a required risk evidence quote cannot be verified."""


# ---------------------------------------------------------------------------
# Account identity helpers
# ---------------------------------------------------------------------------


def get_account_identifier(account: dict) -> str | None:
    """Return the account's identifier using flexible candidate keys.

    Checks :data:`ACCOUNT_ID_KEYS` in order, coerces to string, strips
    whitespace, and returns the first non-empty value. Returns ``None`` if no
    ID-like key exists.
    """
    if not isinstance(account, dict):
        return None
    for key in ACCOUNT_ID_KEYS:
        if key in account and account[key] is not None:
            value = str(account[key]).strip()
            if value:
                return value
    return None


def find_account_by_id(accounts: list[dict], account_id: str) -> dict:
    """Return the account whose identifier exactly matches *account_id*.

    Raises:
        AccountDataError: if *account_id* is empty or *accounts* is empty.
        AccountNotFoundError: if no account matches.
    """
    account_id = (account_id or "").strip()
    if not account_id:
        raise AccountDataError("Account ID cannot be empty.")
    if not accounts:
        raise AccountDataError("No accounts were loaded from the official dataset.")

    for account in accounts:
        identifier = get_account_identifier(account)
        if identifier is not None and identifier == account_id:
            return account
    raise AccountNotFoundError(f"Account not found: {account_id}")


def ticket_matches_account(ticket: dict, account_id: str) -> bool:
    """Return True if *ticket* belongs to *account_id* via flexible keys."""
    if not isinstance(ticket, dict):
        return False
    account_id = (account_id or "").strip()
    if not account_id:
        return False
    for key in TICKET_ACCOUNT_KEYS:
        if key in ticket and ticket[key] is not None:
            if str(ticket[key]).strip() == account_id:
                return True
    return False


# ---------------------------------------------------------------------------
# Date parsing and 90-day filtering
# ---------------------------------------------------------------------------


def _utc_now_naive() -> datetime:
    """Return the current UTC time as a timezone-naive datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_dt_string(value: str) -> datetime | None:
    """Parse a date/datetime string into a timezone-naive datetime, or None."""
    value = value.strip()
    if not value:
        return None
    formats = (
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%fZ",
    )
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except (ValueError, TypeError):
            continue
    # Fallback: ISO-8601 with explicit offset (e.g. "+00:00").
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def parse_ticket_date(ticket: dict) -> datetime | None:
    """Return the ticket's date as a naive datetime, or None if absent/invalid."""
    if not isinstance(ticket, dict):
        return None
    for key in DATE_KEYS:
        value = ticket.get(key)
        if isinstance(value, str):
            parsed = _parse_dt_string(value)
            if parsed is not None:
                return parsed
    return None


def infer_reference_date(tickets: list[dict]) -> datetime:
    """Return the latest valid ticket date, or the current UTC time.

    Using the dataset's latest ticket date keeps "last 90 days" deterministic
    for synthetic datasets that do not align with the real current date.
    """
    dates = [d for d in (parse_ticket_date(t) for t in tickets) if d is not None]
    if dates:
        return max(dates)
    return _utc_now_naive()


def filter_tickets_last_90_days(
    tickets: list[dict],
    reference_date: datetime | None = None,
) -> list[dict]:
    """Return tickets within 90 days of *reference_date* (new list, no mutation).

    Tickets without a valid date are included only when there are no dated
    tickets at all.
    """
    parsed = [(parse_ticket_date(t), t) for t in tickets]
    has_dates = any(date is not None for date, _ in parsed)
    if not has_dates:
        return list(tickets)

    if reference_date is None:
        reference_date = infer_reference_date(tickets)
    cutoff = reference_date - timedelta(days=90)

    result: list[dict] = []
    for date, ticket in parsed:
        if date is not None and cutoff <= date <= reference_date:
            result.append(ticket)
    return result


# ---------------------------------------------------------------------------
# Deterministic ticket sorting
# ---------------------------------------------------------------------------


def get_ticket_identifier(ticket: dict) -> str | None:
    """Return the ticket's identifier using flexible candidate keys, or None."""
    if not isinstance(ticket, dict):
        return None
    for key in TICKET_ID_KEYS:
        if key in ticket and ticket[key] is not None:
            value = str(ticket[key]).strip()
            if value:
                return value
    return None


def sort_tickets_deterministically(tickets: list[dict]) -> list[dict]:
    """Return tickets sorted by date desc (missing last), then ID asc, then JSON."""

    def sort_key(ticket: dict):
        date = parse_ticket_date(ticket)
        has_date = date is not None
        timestamp = date.timestamp() if has_date else 0.0
        ticket_id = get_ticket_identifier(ticket) or ""
        fallback = json.dumps(ticket, sort_keys=True, default=str)
        # Dated tickets first (0), most recent first (-timestamp), then ID asc.
        return (0 if has_date else 1, -timestamp, ticket_id, fallback)

    return sorted(tickets, key=sort_key)


# ---------------------------------------------------------------------------
# Ticket text extraction
# ---------------------------------------------------------------------------


def flatten_text_values(obj) -> list[str]:
    """Flatten nested strings/numbers from dicts/lists into a list of strings."""
    if obj is None:
        return []
    if isinstance(obj, bool):
        return [str(obj)]
    if isinstance(obj, (int, float)):
        return [str(obj)]
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        flat: list[str] = []
        for value in obj.values():
            flat.extend(flatten_text_values(value))
        return flat
    if isinstance(obj, (list, tuple)):
        flat = []
        for item in obj:
            flat.extend(flatten_text_values(item))
        return flat
    return [str(obj)]


def extract_ticket_text(ticket: dict) -> str:
    """Return normalized, quote-preserving text for a ticket.

    Combines meaningful fields when present; otherwise flattens the whole
    object. Whitespace is collapsed but wording is preserved so direct-quote
    checks remain reliable.
    """
    if not isinstance(ticket, dict):
        parts = flatten_text_values(ticket)
    else:
        parts = []
        for field in TICKET_TEXT_FIELDS:
            if field in ticket:
                parts.extend(flatten_text_values(ticket[field]))
        if not parts:
            parts = flatten_text_values(ticket)

    text = " ".join(part for part in parts if part and part.strip())
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Direct quote verification
# ---------------------------------------------------------------------------


def normalize_for_quote_match(text: str) -> str:
    """Collapse whitespace, strip, and lowercase for case-insensitive matching."""
    return re.sub(r"\s+", " ", text or "").strip().lower()


def verify_evidence_quote(
    evidence_quote: str,
    tickets: list[dict],
) -> tuple[bool, str | None]:
    """Return ``(found, ticket_id)`` if *evidence_quote* appears in any ticket."""
    normalized_quote = normalize_for_quote_match(evidence_quote or "")
    if not normalized_quote:
        return (False, None)
    for ticket in tickets:
        ticket_text = normalize_for_quote_match(extract_ticket_text(ticket))
        if normalized_quote in ticket_text:
            return (True, get_ticket_identifier(ticket))
    return (False, None)


def _coerce_risk_flag(flag: dict, quote: str, ticket_id: str | None) -> dict:
    """Return a risk-flag dict with valid, non-empty required fields."""
    signal = str(flag.get("risk_type") or flag.get("signal") or "other").strip() or "other"
    severity = str(flag.get("severity") or "").strip().lower()
    if severity not in ("low", "medium", "high"):
        severity = _SEVERITY_FOR_SIGNAL.get(signal, "medium")
    summary = str(flag.get("summary") or "").strip()
    if not summary:
        summary = f"Risk evidence detected in ticket text: {quote[:120]}"
    resolved_ticket_id = flag.get("ticket_id") or ticket_id
    return {
        "risk_type": signal,
        "severity": severity,
        "summary": summary,
        "evidence_quote": quote,
        "ticket_id": str(resolved_ticket_id).strip() if resolved_ticket_id else None,
    }


def sanitize_risk_flags(flags: list[dict], tickets: list[dict]) -> list[dict]:
    """Keep only flags whose evidence quote is verifiable against source tickets.

    Flags without a quote, or whose quote does not appear in any ticket, are
    dropped. Missing ticket IDs are filled in from the matched ticket. Quotes
    are never invented or replaced.
    """
    sanitized: list[dict] = []
    for flag in flags:
        if not isinstance(flag, dict):
            continue
        quote = str(flag.get("evidence_quote") or "").strip()
        if not quote:
            continue
        found, ticket_id = verify_evidence_quote(quote, tickets)
        if not found:
            continue
        sanitized.append(_coerce_risk_flag(flag, quote, ticket_id))
    return sanitized


# ---------------------------------------------------------------------------
# Local risk quote candidate detection
# ---------------------------------------------------------------------------


def _extract_quote_for_term(text: str, term: str) -> str:
    """Return the sentence (or short window) containing *term* from *text*."""
    lowered_term = term.lower()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for sentence in sentences:
        if lowered_term in sentence.lower():
            return sentence.strip()[:_MAX_QUOTE_CHARS]
    # No sentence boundary matched — fall back to a window around the term.
    index = text.lower().find(lowered_term)
    if index == -1:
        return text.strip()[:_MAX_QUOTE_CHARS]
    start = max(0, index - 100)
    end = min(len(text), index + len(term) + 150)
    return text[start:end].strip()[:_MAX_QUOTE_CHARS]


def detect_risk_quote_candidates(tickets: list[dict], limit: int = 10) -> list[dict]:
    """Detect local churn/escalation risk quote candidates from ticket text.

    Returns at most *limit* candidates, one per ticket (first matching term),
    each with an exact substring quote (never paraphrased).
    """
    candidates: list[dict] = []
    for ticket in tickets:
        if len(candidates) >= limit:
            break
        text = extract_ticket_text(ticket)
        if not text:
            continue
        lowered = text.lower()
        for term, signal in RISK_TERMS:
            if term in lowered:
                candidates.append(
                    {
                        "ticket_id": get_ticket_identifier(ticket),
                        "signal": signal,
                        "quote": _extract_quote_for_term(text, term),
                        "source": "ticket_text",
                    }
                )
                break
    return candidates[:limit]


# ---------------------------------------------------------------------------
# Prompt construction helpers
# ---------------------------------------------------------------------------


def format_account_for_prompt(account: dict) -> str:
    """Return a stable JSON rendering of the account for prompting."""
    return json.dumps(account, indent=2, sort_keys=True, default=str)


def format_tickets_for_prompt(tickets: list[dict]) -> str:
    """Return readable, numbered ticket blocks for prompting."""
    if not tickets:
        return "No tickets were found for this account in the last 90 days."
    blocks: list[str] = []
    for index, ticket in enumerate(tickets, start=1):
        ticket_id = get_ticket_identifier(ticket) or "unknown"
        date = parse_ticket_date(ticket)
        date_str = date.isoformat() if date is not None else "unknown"
        blocks.append(
            f"[TICKET {index}]\n"
            f"ID: {ticket_id}\n"
            f"Date: {date_str}\n"
            f"Text: {extract_ticket_text(ticket)}"
        )
    return "\n\n".join(blocks)


def format_risk_candidates_for_prompt(candidates: list[dict]) -> str:
    """Return readable risk candidate blocks, or an explicit empty message."""
    if not candidates:
        return "No local churn/escalation quote candidates were detected."
    blocks: list[str] = []
    for index, candidate in enumerate(candidates, start=1):
        blocks.append(
            f"[CANDIDATE {index}]\n"
            f"Ticket ID: {candidate.get('ticket_id')}\n"
            f"Signal: {candidate.get('signal')}\n"
            f"Quote: {candidate.get('quote')}"
        )
    return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# Post-processing
# ---------------------------------------------------------------------------


def _default_talking_points(risk_flags: list[dict]) -> list[str]:
    """Return safe deterministic talking points based on detected risks."""
    points = ["Review recent ticket themes from the last 90 days."]
    if risk_flags:
        points.append(
            "Discuss the detected churn/escalation risks and a concrete recovery plan."
        )
    points.append(_DEFAULT_TALKING_POINT)
    return points


def post_process_brief_response(
    raw: dict,
    account_id: str,
    tickets: list[dict],
    prompt_version: str,
) -> dict:
    """Coerce and sanitize raw LLM output into a valid brief dict."""
    result: dict = dict(raw or {})

    result["account_id"] = account_id
    result["prompt_version"] = (
        prompt_version or result.get("prompt_version") or "account_summary_v1"
    )

    risks = result.get("open_risks_and_flagged_issues")
    if not isinstance(risks, list):
        risks = []
    sanitized_risks = sanitize_risk_flags(risks, tickets)
    result["open_risks_and_flagged_issues"] = sanitized_risks

    talking_points = result.get("recommended_talking_points")
    if not isinstance(talking_points, list):
        talking_points = []
    talking_points = [str(p).strip() for p in talking_points if str(p).strip()]
    if not talking_points:
        talking_points = _default_talking_points(sanitized_risks)
    result["recommended_talking_points"] = talking_points

    executive_summary = str(result.get("executive_summary") or "").strip()
    if not executive_summary:
        executive_summary = _build_fallback_summary(account_id, tickets, sanitized_risks)
    result["executive_summary"] = executive_summary

    result["ticket_count_used"] = len(tickets)
    result.setdefault("deterministic", True)
    return result


def _build_fallback_summary(
    account_id: str,
    tickets: list[dict],
    risk_flags: list[dict],
) -> str:
    """Return a deterministic 3-sentence executive summary."""
    return (
        f"This account brief for {account_id} was generated by local fallback "
        "logic without an LLM, using only official account and ticket data. "
        f"The account has {len(tickets)} support ticket(s) in the last 90 days. "
        f"{len(risk_flags)} churn or escalation risk signal(s) were verified "
        "against direct ticket quotes."
    )


# ---------------------------------------------------------------------------
# Summariser
# ---------------------------------------------------------------------------


class AccountHealthSummarizer:
    """Generate a deterministic TAM account health brief for one account."""

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        prompt_name: str = "account_summary_v1",
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.prompt_name = prompt_name
        self.llm_client = (
            llm_client if llm_client is not None else LLMClient(settings=self.settings)
        )
        self.prompt_version = self._resolve_prompt_version()

    def _resolve_prompt_version(self) -> str:
        try:
            return get_prompt_version(self.prompt_name, settings=self.settings)
        except PromptError:
            return self.prompt_name

    # -- data loading (overridable for tests) --------------------------------

    def _load_accounts(self) -> list[dict]:
        return load_accounts(self.settings)

    def _load_tickets(self) -> list[dict]:
        return load_tickets(self.settings)

    # -- core flow -----------------------------------------------------------

    def generate_brief(self, account_id: str) -> AccountBriefResponse:
        """Generate a validated account brief for *account_id*."""
        account_id = (account_id or "").strip()
        if not account_id:
            raise AccountDataError("Account ID cannot be empty.")

        # Dataset errors (missing/empty/invalid) propagate so the API layer can
        # map them to a clean 503/400 instead of a fabricated brief.
        accounts = self._load_accounts()
        account = find_account_by_id(accounts, account_id)

        try:
            all_tickets = self._load_tickets()
        except (MissingDatasetError, EmptyDatasetError):
            # The account exists but the tickets file is missing/empty: a brief
            # with no recent tickets is still useful and must not crash.
            all_tickets = []

        account_tickets = [
            ticket for ticket in all_tickets if ticket_matches_account(ticket, account_id)
        ]
        recent = sort_tickets_deterministically(
            filter_tickets_last_90_days(account_tickets)
        )

        # Operate on redacted copies throughout the LLM path so PII never leaves
        # the process, and verification stays consistent with what the LLM saw.
        safe_account = redact_account_payload(account)
        safe_tickets = [redact_ticket_payload(ticket) for ticket in recent]
        candidates = detect_risk_quote_candidates(safe_tickets)

        if not self.llm_client.is_configured():
            return self._fallback_response(account_id, safe_tickets, candidates)

        try:
            prompt = self._build_prompt(account_id, safe_account, safe_tickets, candidates)
            raw = self.llm_client.complete_json(
                prompt,
                system_message=(
                    "You are a deterministic TAM account-health assistant. "
                    "Use only the provided data. Return JSON only."
                ),
            )
        except LLMClientError as exc:
            logger.info("LLM unavailable for account brief; using fallback: %s", exc)
            return self._fallback_response(account_id, safe_tickets, candidates)

        try:
            processed = post_process_brief_response(
                raw, account_id, safe_tickets, self.prompt_version
            )
            return AccountBriefResponse(**processed)
        except (ValidationError, ValueError, KeyError, TypeError) as exc:
            logger.info("LLM brief failed validation; using fallback: %s", exc)
            return self._fallback_response(account_id, safe_tickets, candidates)

    # -- prompt --------------------------------------------------------------

    def _build_prompt(
        self,
        account_id: str,
        account: dict,
        tickets: list[dict],
        candidates: list[dict],
    ) -> str:
        template = load_prompt(self.prompt_name, settings=self.settings)
        return render_prompt(
            template,
            {
                "account_id": account_id,
                "account_summary": format_account_for_prompt(account),
                "tickets_last_90_days": format_tickets_for_prompt(tickets),
                "risk_quote_candidates": format_risk_candidates_for_prompt(candidates),
                "prompt_version": self.prompt_version,
            },
        )

    # -- fallback ------------------------------------------------------------

    def _fallback_response(
        self,
        account_id: str,
        tickets: list[dict],
        candidates: list[dict],
    ) -> AccountBriefResponse:
        """Deterministic local brief used when the LLM is unavailable."""
        risk_flags: list[dict] = []
        for candidate in candidates:
            quote = str(candidate.get("quote") or "").strip()
            if not quote:
                continue
            signal = candidate.get("signal") or "other"
            risk_flags.append(
                {
                    "risk_type": signal,
                    "severity": _SEVERITY_FOR_SIGNAL.get(signal, "medium"),
                    "summary": f"Local detection of a {signal} signal in ticket text.",
                    "evidence_quote": quote,
                    "ticket_id": candidate.get("ticket_id"),
                }
            )
        # Only keep flags whose quotes are verifiable against actual ticket text.
        risk_flags = sanitize_risk_flags(risk_flags, tickets)

        return AccountBriefResponse(
            account_id=account_id,
            executive_summary=_build_fallback_summary(account_id, tickets, risk_flags),
            open_risks_and_flagged_issues=risk_flags,
            recommended_talking_points=_default_talking_points(risk_flags),
            ticket_count_used=len(tickets),
            prompt_version=self.prompt_version,
            deterministic=True,
        )
