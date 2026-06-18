"""Tests for the bonus Streamlit thin UI.

Importing the module must NOT launch the UI, and the public helpers must be
available. No real LLM key or official dataset is required.
"""

from __future__ import annotations


def test_streamlit_app_imports():
    import ui.streamlit_app

    assert hasattr(ui.streamlit_app, "main")


def test_safe_model_dump_with_plain_dict():
    from ui.streamlit_app import safe_model_dump

    payload = {"a": 1, "b": "two"}
    assert safe_model_dump(payload) == payload


def test_safe_model_dump_with_pydantic_model():
    from app.schemas import DatasetNotReadyDetail
    from ui.streamlit_app import safe_model_dump

    model = DatasetNotReadyDetail(missing=["data/tickets.json"])
    dumped = safe_model_dump(model)
    assert dumped["missing"] == ["data/tickets.json"]


def test_render_helpers_exist():
    import ui.streamlit_app as app

    for name in (
        "render_dataset_status",
        "render_ticket_triage",
        "render_account_brief",
        "render_eval_report",
        "render_about",
    ):
        assert callable(getattr(app, name))
