"""Deterministic section-by-section streaming for the Task 2 account brief (bonus).

This is a presentation layer only: it does NOT regenerate or alter the brief.
A completed :class:`~app.schemas.AccountBriefResponse` is split into ordered
newline-delimited JSON (NDJSON) chunks. This approach:

* works with any OpenAI-compatible provider (Groq included) and in fallback mode,
* does not depend on provider token streaming,
* stays fully deterministic, and
* never exposes secrets or raw account/ticket data beyond what the brief carries.
"""

from __future__ import annotations

import json
from typing import Any, Iterator

from app.schemas import AccountBriefResponse


def model_to_dict(obj: Any) -> dict:
    """Convert a Pydantic model (v2 or v1) or plain dict into a dict."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    dict_method = getattr(obj, "dict", None)
    if callable(dict_method):
        return dict_method()
    if isinstance(obj, dict):
        return obj
    raise TypeError(f"Cannot convert {type(obj).__name__} to dict")


def json_line(payload: dict) -> str:
    """Serialize *payload* as a single NDJSON line ending in a newline."""
    return json.dumps(payload, ensure_ascii=False) + "\n"


def stream_account_brief_sections(brief: AccountBriefResponse) -> Iterator[str]:
    """Yield the brief as ordered NDJSON chunks.

    Order: metadata, executive_summary, one chunk per risk, one chunk per
    talking point, then a terminal ``done`` chunk. Every chunk ends with a
    newline and contains only data already present in *brief*.
    """
    data = model_to_dict(brief)

    yield json_line(
        {
            "type": "metadata",
            "account_id": data.get("account_id"),
            "prompt_version": data.get("prompt_version"),
            "ticket_count_used": data.get("ticket_count_used"),
        }
    )

    yield json_line(
        {
            "type": "executive_summary",
            "content": data.get("executive_summary", ""),
        }
    )

    risks = data.get("open_risks_and_flagged_issues") or []
    for index, risk in enumerate(risks, start=1):
        yield json_line({"type": "risk", "index": index, "content": risk})

    talking_points = data.get("recommended_talking_points") or []
    for index, point in enumerate(talking_points, start=1):
        yield json_line({"type": "talking_point", "index": index, "content": point})

    yield json_line({"type": "done"})


def stream_error(error_type: str, message: str) -> Iterator[str]:
    """Yield a controlled error chunk followed by a terminal ``done`` chunk.

    Used so a missing dataset (or other controlled failure) streams a clean
    error instead of crashing or leaking a stack trace.
    """
    yield json_line({"type": "error", "error_type": error_type, "message": message})
    yield json_line({"type": "done"})
