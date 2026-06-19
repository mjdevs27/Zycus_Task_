"""Streamlit thin UI for the US Delivery AI Support tools (bonus).

A lightweight demo a non-technical TAM could use. It reuses the existing
business logic (triage agent, account summariser, eval runner, dataset loader)
and never duplicates it. Importing this module must NOT launch the UI, so all
Streamlit calls live inside functions guarded by ``if __name__ == "__main__"``.

Safety:
* Never displays the API key or any secret value.
* Never creates or suggests fake official data.
* Catches controlled exceptions and shows friendly messages, not stack traces.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# Ensure the repository root (the parent of this ui/ directory) is importable
# so ``import app...`` works no matter where the script is launched from. This
# matters on Streamlit Community Cloud, where the entry script lives in ui/.
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import streamlit as st

from app.account_summarizer import (
    AccountDataError,
    AccountHealthSummarizer,
    AccountNotFoundError,
    AccountSummaryError,
)
from app.config import get_settings
from app.data_loader import (
    EmptyDatasetError,
    InvalidDatasetError,
    MissingDatasetError,
    check_dataset_status,
)
from app.llm_client import MissingLLMConfigurationError
from app.schemas import TicketTriageRequest
from app.streaming import stream_account_brief_sections
from app.triage_agent import TicketTriageAgent

PROJECT_NAME = "US Delivery AI Support Tools"
EVAL_REPORT_JSON = "eval_report.json"

_DATASET_NOT_READY_MESSAGE = (
    "Official dataset is not ready. Place the starter repo `tickets.json`, "
    "`accounts.json`, and Markdown KB docs in the configured paths."
)


# ---------------------------------------------------------------------------
# Deployment: bridge Streamlit Cloud secrets into the environment
# ---------------------------------------------------------------------------

# Settings (app.config) read configuration from environment variables / .env.
# On Streamlit Community Cloud there is no committed .env (it stays gitignored),
# so configuration is supplied via the dashboard "Secrets" box. Copy every
# provided secret into os.environ *before* get_settings() is first called so the
# same code path works locally (.env) and when deployed (st.secrets). Existing
# environment variables are never overwritten (setdefault semantics). Accessing
# st.secrets when none are configured raises, so this is fully guarded and a
# no-op locally.
def bridge_secrets_to_env() -> None:
    """Copy all Streamlit secrets into os.environ without overwriting env vars."""
    try:
        secrets = st.secrets
    except Exception:  # noqa: BLE001 - no secrets configured is fine locally
        return
    try:
        items = list(secrets.items())
    except Exception:  # noqa: BLE001 - empty/unavailable secrets are fine
        return
    for key, value in items:
        if value is None:
            continue
        # Only bridge flat string-like values; nested TOML tables are skipped.
        if isinstance(value, (dict, list)):
            continue
        os.environ.setdefault(str(key), str(value))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def safe_model_dump(obj: Any) -> dict:
    """Convert a Pydantic v2/v1 model or plain dict into a dict."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    dict_method = getattr(obj, "dict", None)
    if callable(dict_method):
        return dict_method()
    if isinstance(obj, dict):
        return obj
    raise TypeError(f"Cannot convert {type(obj).__name__} to dict")


def _provider_label(settings) -> str:
    """Describe the configured provider without revealing any secret."""
    base_url = settings.openai_base_url or "OpenAI default endpoint"
    return f"{base_url} · model `{settings.openai_model}`"


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def render_sidebar() -> str:
    """Render the sidebar and return the selected section name."""
    settings = get_settings()
    st.sidebar.title(PROJECT_NAME)
    st.sidebar.caption("Thin UI demo for Technical Support & TAM teams")

    st.sidebar.markdown("**Model / provider**")
    st.sidebar.write(_provider_label(settings))
    # Never show the key itself — only whether one is present.
    key_state = "configured" if settings.openai_api_key else "not configured"
    st.sidebar.write(f"LLM API key: {key_state}")

    try:
        status = check_dataset_status(settings)
        if status.ready:
            st.sidebar.success("Dataset ready")
        else:
            st.sidebar.warning("Dataset not ready")
    except Exception:  # noqa: BLE001 - sidebar must never crash the app
        st.sidebar.info("Dataset status unavailable")

    return st.sidebar.radio(
        "Navigation",
        [
            "Dataset Status",
            "Ticket Triage",
            "TAM Account Brief",
            "Eval Report",
            "About / Submission Notes",
        ],
    )


# ---------------------------------------------------------------------------
# Section 1 — Dataset status
# ---------------------------------------------------------------------------


def render_dataset_status() -> None:
    st.header("Dataset Status")
    try:
        status = check_dataset_status()
    except Exception:  # noqa: BLE001
        st.error("Could not read dataset status.")
        return

    data = safe_model_dump(status)
    cols = st.columns(2)
    with cols[0]:
        st.metric("Tickets file exists", str(data.get("tickets_file_exists")))
        st.metric("Tickets non-empty", str(data.get("tickets_file_non_empty")))
        st.metric("Accounts file exists", str(data.get("accounts_file_exists")))
        st.metric("Accounts non-empty", str(data.get("accounts_file_non_empty")))
    with cols[1]:
        st.metric("KB dir exists", str(data.get("kb_dir_exists")))
        st.metric("KB docs count", str(data.get("kb_docs_count")))
        st.metric("Ready", str(data.get("ready")))

    st.caption(data.get("message", ""))

    if not data.get("ready"):
        st.warning(_DATASET_NOT_READY_MESSAGE)
        st.info(
            "This tool never fabricates official data. Data-dependent features "
            "fail gracefully until the official files are present."
        )


# ---------------------------------------------------------------------------
# Section 2 — Ticket triage
# ---------------------------------------------------------------------------


def render_ticket_triage() -> None:
    st.header("Task 1 — Ticket Triage")
    subject = st.text_input("Subject")
    body = st.text_area("Body", height=140)
    raw = st.text_area("Or paste raw ticket text (optional, overrides subject/body)", height=120)

    if not st.button("Run triage"):
        return

    raw_text = (raw or "").strip()
    if raw_text:
        request_kwargs = {"text": raw_text}
    else:
        request_kwargs = {"subject": subject, "body": body}

    try:
        request = TicketTriageRequest(**request_kwargs)
    except Exception as exc:  # noqa: BLE001 - validation is a user-input issue
        st.warning(f"Please provide ticket text: {exc}")
        return

    try:
        agent = TicketTriageAgent()
        result = agent.triage(request)
    except MissingLLMConfigurationError:
        st.warning("LLM is not configured; showing the deterministic local fallback.")
        return
    except Exception:  # noqa: BLE001 - never show a stack trace
        st.error("An unexpected error occurred while triaging the ticket.")
        return

    data = safe_model_dump(result)
    st.subheader("Result")
    st.write(f"**Product area:** {data.get('product_area')}")
    st.write(f"**Issue category:** {data.get('issue_category')}")
    st.write(f"**Urgency tier:** {data.get('urgency_tier')}")
    st.write(f"**Recommended team:** {data.get('recommended_team')}")
    st.write(f"**Prompt version:** {data.get('prompt_version')}")
    if not data.get("deterministic", True):
        st.caption("Generated with the LLM.")
    else:
        st.caption("")

    st.markdown("**Reasoning**")
    st.write(data.get("reasoning"))

    st.markdown("**Draft first response**")
    st.write(data.get("draft_first_response"))

    known = data.get("known_issue_match") or {}
    st.markdown("**Known issue match**")
    if known.get("matched"):
        st.write(f"Matched: {known.get('doc_title')} ({known.get('doc_path')})")
        st.write(known.get("match_reason"))
    else:
        st.write("No known issue matched.")

    retrieved = data.get("retrieved_docs") or []
    st.markdown("**Retrieved docs**")
    if retrieved:
        for doc in retrieved:
            st.write(f"- {doc.get('title')} (`{doc.get('path')}`, score {doc.get('score')})")
    else:
        st.caption("No KB docs retrieved (knowledge base may be missing).")


# ---------------------------------------------------------------------------
# Section 3 — Account brief
# ---------------------------------------------------------------------------


def _render_risk(risk: dict) -> None:
    st.write(f"- **{risk.get('risk_type')}** ({risk.get('severity')})")
    st.write(f"  - {risk.get('summary')}")
    st.write(f"  - Evidence: \"{risk.get('evidence_quote')}\"")
    if risk.get("ticket_id"):
        st.write(f"  - Ticket: {risk.get('ticket_id')}")


def render_account_brief() -> None:
    st.header("Task 2 — TAM Account Brief")
    account_id = st.text_input("Account ID")
    use_streaming = st.checkbox("Use streaming display", value=False)

    if not st.button("Generate brief"):
        return

    if not (account_id or "").strip():
        st.warning("Enter an account ID from the official accounts dataset.")
        return

    try:
        summarizer = AccountHealthSummarizer()
        brief = summarizer.generate_brief(account_id)
    except AccountNotFoundError:
        st.warning(
            "That account ID was not found in the official dataset. "
            "No fake account data is created."
        )
        return
    except (MissingDatasetError, EmptyDatasetError, InvalidDatasetError):
        st.warning(_DATASET_NOT_READY_MESSAGE)
        return
    except MissingLLMConfigurationError:
        st.warning("LLM is not configured; showing the deterministic local fallback.")
        return
    except (AccountDataError, AccountSummaryError) as exc:
        st.warning(str(exc))
        return
    except Exception:  # noqa: BLE001 - never show a stack trace
        st.error("An unexpected error occurred while generating the account brief.")
        return

    data = safe_model_dump(brief)

    if use_streaming:
        st.subheader("Streaming brief")
        placeholder = st.empty()
        rendered: list[str] = []
        for chunk in stream_account_brief_sections(brief):
            event = json.loads(chunk)
            etype = event.get("type")
            if etype == "metadata":
                rendered.append(
                    f"**Account:** {event.get('account_id')} · "
                    f"prompt `{event.get('prompt_version')}` · "
                    f"tickets used {event.get('ticket_count_used')}"
                )
            elif etype == "executive_summary":
                rendered.append(f"**Executive summary:** {event.get('content')}")
            elif etype == "risk":
                risk = event.get("content", {})
                rendered.append(
                    f"**Risk {event.get('index')}:** {risk.get('risk_type')} "
                    f"({risk.get('severity')}) — \"{risk.get('evidence_quote')}\""
                )
            elif etype == "talking_point":
                rendered.append(f"**Talking point {event.get('index')}:** {event.get('content')}")
            elif etype == "done":
                rendered.append("_done_")
            placeholder.markdown("\n\n".join(rendered))
        return

    st.subheader("Executive summary")
    st.write(data.get("executive_summary"))
    st.caption(
        f"Prompt version: {data.get('prompt_version')} · "
        f"tickets used: {data.get('ticket_count_used')}"
    )

    st.subheader("Open risks and flagged issues")
    risks = data.get("open_risks_and_flagged_issues") or []
    if risks:
        for risk in risks:
            _render_risk(risk)
    else:
        st.caption("No risks flagged (every risk requires a verified ticket quote).")

    st.subheader("Recommended talking points")
    points = data.get("recommended_talking_points") or []
    if points:
        for point in points:
            st.write(f"- {point}")
    else:
        st.caption("No talking points available.")


# ---------------------------------------------------------------------------
# Section 4 — Eval report
# ---------------------------------------------------------------------------


def render_eval_report() -> None:
    st.header("Task 3 — Evaluation Report")

    cols = st.columns(2)
    run_clicked = cols[0].button("Run evals")
    refresh_clicked = cols[1].button("Load/refresh existing report")

    if run_clicked:
        try:
            from evals.run_evals import run_all_evals

            with st.spinner("Running evaluation harness..."):
                run_all_evals()
            st.success("Evaluation complete.")
        except Exception:  # noqa: BLE001 - never show a stack trace
            st.error("An unexpected error occurred while running evaluations.")

    report_path = Path(EVAL_REPORT_JSON)
    if not report_path.exists():
        st.info(
            "No eval report found yet. Click **Run evals** to generate "
            "`eval_report.json` and `eval_report.md`."
        )
        return

    if refresh_clicked or run_clicked or report_path.exists():
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            st.error("Could not read the existing eval report.")
            return

        cols = st.columns(5)
        cols[0].metric("Total", data.get("total_cases"))
        cols[1].metric("Passed", data.get("passed_cases"))
        cols[2].metric("Failed", data.get("failed_cases"))
        cols[3].metric("Avg score", data.get("average_score"))
        cols[4].metric("Dataset ready", str(data.get("dataset_ready")))

        if not data.get("dataset_ready"):
            st.warning(
                "Dataset is not ready, so account cases requiring official data "
                "failed gracefully. This is expected and shown honestly."
            )

        results = data.get("results") or []
        if results:
            st.dataframe(results, use_container_width=True)


# ---------------------------------------------------------------------------
# Section 5 — About
# ---------------------------------------------------------------------------


def render_about() -> None:
    st.header("About / Submission Notes")
    st.markdown(
        """
This project implements **Task 1** (ticket triage), **Task 2** (TAM account
brief), **Task 3** (eval harness), **Task 4** (design note), and selected bonus
items (this UI, streaming, CI, prompt versioning).

- It uses **only** the official mock dataset when available.
- It does **not** introduce external data or fabricate official records.
- Real API keys must stay in `.env` only.
- `.env.example` contains placeholders only.
"""
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    st.set_page_config(page_title=PROJECT_NAME, page_icon="🎫", layout="wide")
    bridge_secrets_to_env()
    section = render_sidebar()
    if section == "Dataset Status":
        render_dataset_status()
    elif section == "Ticket Triage":
        render_ticket_triage()
    elif section == "TAM Account Brief":
        render_account_brief()
    elif section == "Eval Report":
        render_eval_report()
    else:
        render_about()


if __name__ == "__main__":
    main()
