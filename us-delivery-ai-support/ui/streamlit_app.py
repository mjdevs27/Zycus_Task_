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

# Ensure the project root (the parent of this ui/ directory) is importable
# so ``import app...`` works no matter where the script is launched from. This
# matters on Streamlit Community Cloud, where the entry script lives in ui/.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Load the local .env (if present) before importing any app module that reads
# settings. ``override=False`` keeps real environment variables / Streamlit
# secrets authoritative. On Streamlit Cloud there is no .env and this is a
# harmless no-op; configuration comes from the secrets bridge instead.
import streamlit as st  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

# ---------------------------------------------------------------------------
# Configuration bootstrap — MUST run before importing any app.* module.
# ---------------------------------------------------------------------------
#
# app.config builds Settings from environment variables / .env. If Settings is
# constructed before the configuration source is in os.environ, it falls back
# to defaults (gpt-4o-mini, no key). So we populate the environment here, at the
# very top of the file, before the first app import:
#
#   1. Local development -> load the project-root .env (does not override real
#      environment variables that are already set).
#   2. Streamlit Community Cloud -> there is no .env; configuration is provided
#      via the dashboard "Secrets" box. Copy those secrets into os.environ.
#      Secrets are authoritative on the cloud, so they overwrite here.
#
# The API key is never printed.
load_dotenv(_PROJECT_ROOT / ".env", override=False)

try:
    for _key, _value in st.secrets.items():
        if _value is None or isinstance(_value, (dict, list)):
            continue
        os.environ[str(_key)] = str(_value)
except Exception:  # noqa: BLE001 - no secrets configured (e.g. local run) is fine
    pass

from app.account_summarizer import (  # noqa: E402
    AccountDataError,
    AccountHealthSummarizer,
    AccountNotFoundError,
    AccountSummaryError,
)
from app.config import get_settings  # noqa: E402
from app.data_loader import (  # noqa: E402
    EmptyDatasetError,
    InvalidDatasetError,
    MissingDatasetError,
    check_dataset_status,
)
from app.llm_client import MissingLLMConfigurationError  # noqa: E402
from app.schemas import TicketTriageRequest  # noqa: E402
from app.streaming import stream_account_brief_sections  # noqa: E402
from app.triage_agent import TicketTriageAgent  # noqa: E402

PROJECT_NAME = "US Delivery AI Support Tools"

_DATASET_NOT_READY_MESSAGE = (
    "Official dataset is not ready. Place the starter repo `tickets.json`, "
    "`accounts.json`, and Markdown KB docs in the configured paths."
)


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
    base_url = settings.openai_base_url
    if base_url:
        if "groq" in base_url.lower():
            provider = "Groq OpenAI-compatible endpoint"
        else:
            provider = "OpenAI-compatible endpoint"
    else:
        provider = "OpenAI default endpoint"
    return f"{provider} · model `{settings.openai_model}`"


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

    # Safe diagnostics: booleans and non-secret values only, never the key.
    with st.sidebar.expander("Config debug", expanded=False):
        st.write("OPENAI_API_KEY loaded:", bool(settings.openai_api_key))
        st.write("OPENAI_BASE_URL loaded:", bool(settings.openai_base_url))
        st.write("OPENAI_MODEL:", settings.openai_model)
        st.write("APP_ENV:", settings.app_env)

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
    except Exception as exc:  # noqa: BLE001 - never show a stack trace in prod
        st.error("An unexpected error occurred while triaging the ticket.")
        # Surface the underlying error only in development to aid debugging;
        # production submissions never expose a stack trace.
        if get_settings().app_env == "development":
            with st.expander("Debug details (development only)"):
                st.exception(exc)
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
        except Exception as exc:  # noqa: BLE001 - never show a raw trace in prod
            st.error("An unexpected error occurred while running evaluations.")
            if get_settings().app_env == "development":
                with st.expander("Debug details (development only)"):
                    st.exception(exc)

    # Read the report from the configured (project-root absolute) path so the
    # UI finds it regardless of the working directory it was launched from.
    report_path = Path(get_settings().eval_report_json)
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

        total = data.get("total_cases") or 0
        passed = data.get("passed_cases") or 0
        pass_rate = f"{(passed / total * 100):.0f}%" if total else "—"

        cols = st.columns(6)
        cols[0].metric("Total", total)
        cols[1].metric("Passed", passed)
        cols[2].metric("Failed", data.get("failed_cases"))
        cols[3].metric("Pass rate", pass_rate)
        cols[4].metric("Avg score", data.get("average_score"))
        cols[5].metric("Dataset ready", str(data.get("dataset_ready")))

        if not data.get("dataset_ready"):
            st.warning(
                "Dataset is not ready, so account cases requiring official data "
                "failed gracefully. This is expected and shown honestly."
            )

        results = data.get("results") or []
        if results:
            import pandas as pd

            rows = [
                {
                    "ID": r.get("id"),
                    "Task": r.get("task"),
                    "Name": r.get("name"),
                    "Passed": bool(r.get("passed")),
                    "Score": r.get("score"),
                    "Adversarial": bool(r.get("adversarial")),
                    "Notes": "; ".join(r.get("notes") or []),
                }
                for r in results
            ]
            df = pd.DataFrame(rows, columns=[
                "ID", "Task", "Name", "Passed", "Score", "Adversarial", "Notes",
            ])

            st.subheader(f"Results ({len(df)} cases)")
            # Static table: always renders every row, no interactive/Arrow quirks.
            st.table(df)

            st.download_button(
                "Download CSV",
                data=df.to_csv(index=False),
                file_name="eval_report.csv",
                mime="text/csv",
            )
        else:
            st.info("The report contains no result rows.")


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
