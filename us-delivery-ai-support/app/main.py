"""FastAPI application for the US Delivery AI Support tools.

Exposes Task 1 (ticket triage), Task 2 (TAM account brief), and a Task 3 eval
trigger. The app starts even when the official dataset or the LLM API key are
missing: ``/`` , ``/health`` and ``/dataset/status`` never depend on either,
and data-dependent endpoints return clean structured JSON errors instead of
raw tracebacks.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from app.account_summarizer import (
    AccountDataError,
    AccountHealthSummarizer,
    AccountNotFoundError,
    AccountSummaryError,
)
from app.data_loader import (
    EmptyDatasetError,
    InvalidDatasetError,
    MissingDatasetError,
    check_dataset_status,
)
from app.llm_client import MissingLLMConfigurationError
from app.schemas import (
    AccountBriefResponse,
    DatasetStatus,
    TicketTriageRequest,
    TicketTriageResponse,
)
from app.streaming import stream_account_brief_sections, stream_error
from app.triage_agent import TicketTriageAgent, TriageError

logger = logging.getLogger("app.main")

SERVICE_NAME = "us-delivery-ai-support"
SERVICE_VERSION = "0.1.0"

app = FastAPI(
    title="US Delivery AI Support Tools",
    description="AI triage and TAM account brief service for the internship task round.",
    version=SERVICE_VERSION,
)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def raise_api_error(
    status_code: int,
    error_type: str,
    message: str,
    hint: str | None = None,
) -> None:
    """Raise an ``HTTPException`` with a consistent structured detail payload."""
    detail: dict[str, str] = {"type": error_type, "message": message}
    if hint is not None:
        detail["hint"] = hint
    raise HTTPException(status_code=status_code, detail=detail)


_DATASET_HINT = (
    "Place the official starter repo dataset files in data/ and knowledge-base/."
)


# ---------------------------------------------------------------------------
# Service / health endpoints (never depend on dataset or LLM key)
# ---------------------------------------------------------------------------


@app.get("/")
def root() -> dict:
    """Simple service index."""
    return {
        "service": SERVICE_NAME,
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
        "dataset_status": "/dataset/status",
    }


@app.get("/health")
def health() -> dict:
    """Basic app health. Always works; no dataset or API key required."""
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
    }


@app.get("/dataset/status", response_model=DatasetStatus)
def dataset_status() -> DatasetStatus:
    """Report whether the official dataset is ready. Not-ready is not an error."""
    return check_dataset_status()


# ---------------------------------------------------------------------------
# Task 1 — triage
# ---------------------------------------------------------------------------


@app.post("/triage", response_model=TicketTriageResponse)
def triage(request: TicketTriageRequest) -> TicketTriageResponse:
    """Triage one support ticket. Falls back locally when no LLM is configured."""
    try:
        agent = TicketTriageAgent()
        return agent.triage(request)
    except TriageError as exc:
        raise_api_error(400, "BadRequest", str(exc))
    except ValueError as exc:
        raise_api_error(400, "BadRequest", str(exc))
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - never leak a traceback
        logger.error("Unexpected triage error: %s", type(exc).__name__)
        raise_api_error(
            500,
            "InternalServerError",
            "An unexpected error occurred while triaging the ticket.",
        )


# ---------------------------------------------------------------------------
# Task 2 — account brief
# ---------------------------------------------------------------------------


@app.post("/accounts/{account_id}/brief", response_model=AccountBriefResponse)
def account_brief(account_id: str) -> AccountBriefResponse:
    """Generate a TAM account health brief for *account_id*."""
    try:
        summarizer = AccountHealthSummarizer()
        return summarizer.generate_brief(account_id)
    except AccountNotFoundError as exc:
        raise_api_error(404, "AccountNotFound", str(exc))
    except AccountDataError as exc:
        raise_api_error(400, "AccountDataError", str(exc))
    except (MissingDatasetError, EmptyDatasetError) as exc:
        raise_api_error(503, "DatasetNotReady", str(exc), hint=_DATASET_HINT)
    except InvalidDatasetError as exc:
        raise_api_error(503, "DatasetInvalid", str(exc), hint=_DATASET_HINT)
    except MissingLLMConfigurationError as exc:
        raise_api_error(503, "LLMNotConfigured", str(exc))
    except AccountSummaryError as exc:
        raise_api_error(400, "AccountSummaryError", str(exc))
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - never leak a traceback
        logger.error("Unexpected account brief error: %s", type(exc).__name__)
        raise_api_error(
            500,
            "InternalServerError",
            "An unexpected error occurred while generating the account brief.",
        )


# ---------------------------------------------------------------------------
# Task 2 — account brief (streaming, bonus)
# ---------------------------------------------------------------------------


@app.post("/accounts/{account_id}/brief/stream")
def account_brief_stream(account_id: str) -> StreamingResponse:
    """Stream a TAM account brief section-by-section as NDJSON.

    Deterministic presentation-layer streaming: the brief is generated in full
    via the existing summariser, then emitted section-by-section. Controlled
    failures (missing dataset, unknown account) stream an error chunk instead of
    crashing, and stack traces are never exposed.
    """

    def generate():
        try:
            summarizer = AccountHealthSummarizer()
            brief = summarizer.generate_brief(account_id)
        except AccountNotFoundError as exc:
            yield from stream_error("AccountNotFound", str(exc))
            return
        except AccountDataError as exc:
            yield from stream_error("AccountDataError", str(exc))
            return
        except (MissingDatasetError, EmptyDatasetError) as exc:
            yield from stream_error("DatasetNotReady", str(exc))
            return
        except InvalidDatasetError as exc:
            yield from stream_error("DatasetInvalid", str(exc))
            return
        except MissingLLMConfigurationError as exc:
            yield from stream_error("LLMNotConfigured", str(exc))
            return
        except AccountSummaryError as exc:
            yield from stream_error("AccountSummaryError", str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - never leak a traceback
            logger.error("Unexpected account stream error: %s", type(exc).__name__)
            yield from stream_error(
                "InternalServerError",
                "An unexpected error occurred while generating the account brief.",
            )
            return
        yield from stream_account_brief_sections(brief)

    return StreamingResponse(generate(), media_type="application/x-ndjson")


# ---------------------------------------------------------------------------
# Task 3 — eval runner trigger
# ---------------------------------------------------------------------------


@app.post("/evals/run")
def run_evals_endpoint() -> dict:
    """Run the evaluation harness and return a summary plus report paths."""
    try:
        # Imported lazily so app startup never depends on the eval module.
        from evals.run_evals import run_all_evals

        report = run_all_evals()
        return {
            "message": "Evaluation completed.",
            "report_path_json": "eval_report.json",
            "report_path_md": "eval_report.md",
            "summary": {
                "total_cases": report.total_cases,
                "passed_cases": report.passed_cases,
                "failed_cases": report.failed_cases,
                "average_score": report.average_score,
                "dataset_ready": report.dataset_ready,
            },
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - never leak a traceback
        logger.error("Unexpected eval run error: %s", type(exc).__name__)
        raise_api_error(
            500,
            "InternalServerError",
            "An unexpected error occurred while running evaluations.",
        )
