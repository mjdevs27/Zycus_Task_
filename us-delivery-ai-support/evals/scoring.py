"""Deterministic, rule-based scoring engine for Task 3 evaluation.

Each case is scored on a 0-1 quality scale and marked pass/fail (threshold
0.70). Scoring is fully deterministic and requires no LLM or external data;
LLM-as-judge is intentionally not used so tests and CI stay reproducible.
"""

from __future__ import annotations

import re

from app.schemas import EvalCaseResult

PASS_THRESHOLD = 0.70
VALID_TIERS = {"P1", "P2", "P3", "P4"}
VALID_TASKS = {"triage", "account_summary"}

_DEFAULT_TRIAGE_FIELDS = [
    "product_area",
    "issue_category",
    "urgency_tier",
    "reasoning",
    "known_issue_match",
    "recommended_team",
    "draft_first_response",
]
_DEFAULT_ACCOUNT_FIELDS = [
    "account_id",
    "executive_summary",
    "open_risks_and_flagged_issues",
    "recommended_talking_points",
]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def to_plain_dict(obj) -> dict:
    """Convert a Pydantic model (v2 or v1) or dict into a plain dict."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
        return obj.dict()
    if isinstance(obj, dict):
        return obj
    raise TypeError(f"Cannot convert {type(obj).__name__} to dict")


def count_sentences(text: str) -> int:
    """Count sentences deterministically using ``.``, ``?`` and ``!``."""
    parts = re.split(r"[.!?]+", text or "")
    return len([part for part in parts if part.strip()])


def has_non_empty_field(output: dict, field: str) -> bool:
    """Return True if *field* exists and is not None/empty string/empty list-dict."""
    if field not in output:
        return False
    value = output[field]
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def extract_all_text_from_obj(obj) -> str:
    """Flatten nested dict/list/string values into a single text blob."""
    parts: list[str] = []

    def walk(node) -> None:
        if node is None:
            return
        if isinstance(node, bool):
            parts.append(str(node))
        elif isinstance(node, (int, float)):
            parts.append(str(node))
        elif isinstance(node, str):
            parts.append(node)
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple)):
            for item in node:
                walk(item)
        else:
            parts.append(str(node))

    walk(obj)
    return " ".join(parts)


def quote_exists_in_tickets(quote: str, source_tickets: list[dict]) -> bool:
    """Return True if *quote* appears in the flattened source ticket text."""
    normalized_quote = re.sub(r"\s+", " ", quote or "").strip().lower()
    if not normalized_quote:
        return False
    haystack = re.sub(
        r"\s+", " ", extract_all_text_from_obj(source_tickets)
    ).strip().lower()
    return normalized_quote in haystack


def clamp_score(score: float) -> float:
    """Clamp *score* into [0, 1] and round to 3 decimals."""
    if score < 0:
        score = 0.0
    elif score > 1:
        score = 1.0
    return round(float(score), 3)


# ---------------------------------------------------------------------------
# Triage scorer
# ---------------------------------------------------------------------------


def score_triage_case(case: dict, output: dict) -> tuple[float, bool, list[str]]:
    """Score a Task 1 triage output. Returns ``(score, passed, notes)``."""
    criteria = case.get("acceptance_criteria") or {}
    notes: list[str] = []
    score = 0.0

    # Required fields present: 0.30
    required = criteria.get("required_fields") or _DEFAULT_TRIAGE_FIELDS
    present = [field for field in required if has_non_empty_field(output, field)]
    score += 0.30 * (len(present) / len(required) if required else 1.0)
    for field in required:
        if field not in present:
            notes.append(f"Missing required field: {field}")

    # Urgency valid/accepted: 0.20
    urgency = output.get("urgency_tier")
    if urgency in VALID_TIERS:
        allowed = criteria.get("allowed_urgency")
        if allowed and urgency not in allowed:
            notes.append(f"Urgency tier {urgency} not in accepted set {allowed}")
            score += 0.10
        else:
            score += 0.20
    else:
        notes.append(f"Urgency tier {urgency} is invalid")

    # Reasoning useful: 0.15
    if has_non_empty_field(output, "reasoning"):
        score += 0.15
    elif criteria.get("must_include_reasoning"):
        notes.append("Reasoning is required but missing")

    # Draft response useful: 0.15
    if has_non_empty_field(output, "draft_first_response"):
        score += 0.15
    elif criteria.get("must_include_draft_response"):
        notes.append("Draft first response is required but missing")

    # Known issue doc path safety: 0.10
    score += _score_known_issue_safety(output, notes)

    # Recommended team present: 0.10
    if has_non_empty_field(output, "recommended_team"):
        score += 0.10
    else:
        notes.append("Missing required field: recommended_team")

    score = clamp_score(score)
    return score, score >= PASS_THRESHOLD, notes


def _score_known_issue_safety(output: dict, notes: list[str]) -> float:
    """Return the known-issue-safety sub-score (0.10 max) and append notes."""
    known = output.get("known_issue_match")
    matched = isinstance(known, dict) and known.get("matched")
    if not matched:
        # No KB claim is the safe default — full credit.
        return 0.10

    doc_path = known.get("doc_path")
    if not doc_path:
        notes.append("Known issue matched but doc_path is missing")
        return 0.0

    retrieved = output.get("retrieved_docs")
    if isinstance(retrieved, list) and retrieved:
        retrieved_paths = {
            doc.get("path") for doc in retrieved if isinstance(doc, dict)
        }
        if doc_path in retrieved_paths:
            return 0.10
        notes.append(
            f"Known issue doc path {doc_path} was not among retrieved docs"
        )
        return 0.0

    # matched=true but no retrieved docs exist to support it — likely hallucinated.
    notes.append(
        "Known issue matched but no retrieved docs exist to support the match"
    )
    return 0.0


# ---------------------------------------------------------------------------
# Account summary scorer
# ---------------------------------------------------------------------------


def score_account_summary_case(
    case: dict,
    output: dict,
    source_tickets: list[dict] | None = None,
) -> tuple[float, bool, list[str]]:
    """Score a Task 2 account-summary output. Returns ``(score, passed, notes)``."""
    criteria = case.get("acceptance_criteria") or {}
    notes: list[str] = []
    score = 0.0

    # Required fields present: 0.25
    required = criteria.get("required_fields") or _DEFAULT_ACCOUNT_FIELDS
    present = [field for field in required if has_non_empty_field(output, field)]
    score += 0.25 * (len(present) / len(required) if required else 1.0)
    for field in required:
        if field not in present:
            notes.append(f"Missing required field: {field}")

    # Executive summary sentence count: 0.20
    if has_non_empty_field(output, "executive_summary"):
        sentence_range = criteria.get("executive_summary_sentence_range")
        if sentence_range:
            count = count_sentences(output.get("executive_summary", ""))
            low, high = sentence_range[0], sentence_range[1]
            if low <= count <= high:
                score += 0.20
            else:
                notes.append(
                    f"Executive summary has {count} sentences, expected "
                    f"{low}–{high}"
                )
        else:
            score += 0.20
    else:
        notes.append("Executive summary is missing")

    # Risk quote requirement: 0.25
    score += _score_risk_quotes(output, source_tickets, notes)

    # Talking points present: 0.15
    talking_points = output.get("recommended_talking_points")
    if (
        isinstance(talking_points, list)
        and talking_points
        and all(str(p).strip() for p in talking_points)
    ):
        minimum = criteria.get("minimum_talking_points")
        if minimum is not None and len(talking_points) < minimum:
            notes.append(
                f"Expected at least {minimum} talking points, got {len(talking_points)}"
            )
        else:
            score += 0.15
    else:
        notes.append("Recommended talking points are missing or empty")

    # Determinism/metadata fields: 0.05
    if has_non_empty_field(output, "prompt_version"):
        score += 0.05
    else:
        notes.append("Missing metadata field: prompt_version")

    # General formatting validity: 0.10
    if (
        isinstance(output.get("executive_summary"), str)
        and isinstance(output.get("open_risks_and_flagged_issues"), list)
        and isinstance(output.get("recommended_talking_points"), list)
    ):
        score += 0.10
    else:
        notes.append("Output formatting is invalid (unexpected field types)")

    score = clamp_score(score)
    return score, score >= PASS_THRESHOLD, notes


def _score_risk_quotes(
    output: dict,
    source_tickets: list[dict] | None,
    notes: list[str],
) -> float:
    """Return the risk-quote sub-score (0.25 max) and append notes.

    An empty risk list earns full credit — absence of risk is not a failure.
    """
    risks = output.get("open_risks_and_flagged_issues")
    if not isinstance(risks, list):
        notes.append("open_risks_and_flagged_issues must be a list")
        return 0.0

    all_ok = True
    for risk in risks:
        quote = risk.get("evidence_quote") if isinstance(risk, dict) else None
        if not quote or not str(quote).strip():
            notes.append("Risk flag missing direct evidence quote")
            all_ok = False
            continue
        if source_tickets is not None and not quote_exists_in_tickets(
            str(quote), source_tickets
        ):
            notes.append("Evidence quote was not found in provided source tickets")
            all_ok = False
    return 0.25 if all_ok else 0.0


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def score_case(
    case: dict,
    output,
    *,
    source_tickets: list[dict] | None = None,
) -> EvalCaseResult:
    """Score one case and return a validated :class:`EvalCaseResult`."""
    task = case.get("task")
    safe_task = task if task in VALID_TASKS else "triage"
    try:
        plain = to_plain_dict(output)
        if task == "triage":
            score, _passed, notes = score_triage_case(case, plain)
        elif task == "account_summary":
            score, _passed, notes = score_account_summary_case(
                case, plain, source_tickets
            )
        else:
            return EvalCaseResult(
                id=case.get("id", "unknown"),
                name=case.get("name", "unknown"),
                task=safe_task,
                passed=False,
                score=0.0,
                notes=[f"Unknown task: {task}"],
                adversarial=bool(case.get("adversarial", False)),
            )
    except Exception as exc:  # noqa: BLE001 - scoring must never raise
        return EvalCaseResult(
            id=case.get("id", "unknown"),
            name=case.get("name", "unknown"),
            task=safe_task,
            passed=False,
            score=0.0,
            notes=[f"Scoring error: {type(exc).__name__}: {exc}"],
            adversarial=bool(case.get("adversarial", False)),
        )

    score = clamp_score(score)
    return EvalCaseResult(
        id=case.get("id", "unknown"),
        name=case.get("name", "unknown"),
        task=safe_task,
        passed=score >= PASS_THRESHOLD,
        score=score,
        notes=notes,
        adversarial=bool(case.get("adversarial", False)),
    )
