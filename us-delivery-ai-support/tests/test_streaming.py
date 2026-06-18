"""Tests for the bonus deterministic account-brief streaming layer."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from app.schemas import AccountBriefResponse, RiskFlag
from app.streaming import (
    json_line,
    model_to_dict,
    stream_account_brief_sections,
    stream_error,
)


def _brief(risks=None, talking_points=None) -> AccountBriefResponse:
    return AccountBriefResponse(
        account_id="acct-123",
        executive_summary="One. Two. Three.",
        open_risks_and_flagged_issues=risks or [],
        recommended_talking_points=talking_points or ["Review recent tickets."],
        ticket_count_used=3,
        prompt_version="account_summary_v1",
    )


def _parse(chunks: list[str]) -> list[dict]:
    return [json.loads(chunk) for chunk in chunks]


# Test 1 — stream emits metadata, executive summary, done; all end with newline
def test_stream_emits_metadata_and_done():
    chunks = list(stream_account_brief_sections(_brief()))
    assert all(chunk.endswith("\n") for chunk in chunks)

    events = _parse(chunks)
    assert events[0]["type"] == "metadata"
    assert events[0]["account_id"] == "acct-123"
    assert events[0]["ticket_count_used"] == 3
    assert any(e["type"] == "executive_summary" for e in events)
    assert events[-1]["type"] == "done"


# Test 2 — one risk chunk per risk
def test_risk_chunks_emitted():
    risks = [
        RiskFlag(
            risk_type="churn_risk",
            severity="high",
            summary="Threatened to cancel.",
            evidence_quote="we may cancel our renewal",
            ticket_id="t1",
        ),
        RiskFlag(
            risk_type="escalation",
            severity="high",
            summary="Asked for a manager.",
            evidence_quote="escalate this to your manager",
            ticket_id="t2",
        ),
    ]
    events = _parse(list(stream_account_brief_sections(_brief(risks=risks))))
    risk_events = [e for e in events if e["type"] == "risk"]
    assert len(risk_events) == 2
    assert risk_events[0]["index"] == 1
    assert risk_events[1]["index"] == 2


# Test 3 — one talking-point chunk per point
def test_talking_point_chunks_emitted():
    points = ["First point.", "Second point."]
    events = _parse(list(stream_account_brief_sections(_brief(talking_points=points))))
    tp_events = [e for e in events if e["type"] == "talking_point"]
    assert len(tp_events) == 2


# Test 4 — stream_error emits error then done
def test_stream_error_emits_error_and_done():
    events = _parse(list(stream_error("DatasetNotReady", "no data")))
    assert events[0]["type"] == "error"
    assert events[0]["error_type"] == "DatasetNotReady"
    assert events[-1]["type"] == "done"


# Test 5 — streaming endpoint exists and returns NDJSON ending in done
def test_streaming_endpoint(monkeypatch):
    from app import main as main_module

    class _FakeSummarizer:
        def __init__(self, *args, **kwargs):
            pass

        def generate_brief(self, account_id):
            return _brief()

    monkeypatch.setattr(main_module, "AccountHealthSummarizer", _FakeSummarizer)

    client = TestClient(app)
    response = client.post("/accounts/test-account/brief/stream")
    assert response.status_code == 200
    assert "done" in response.text


def test_json_line_and_model_to_dict():
    line = json_line({"type": "done"})
    assert line.endswith("\n")
    assert json.loads(line) == {"type": "done"}
    assert model_to_dict({"a": 1}) == {"a": 1}
    assert model_to_dict(_brief())["account_id"] == "acct-123"
