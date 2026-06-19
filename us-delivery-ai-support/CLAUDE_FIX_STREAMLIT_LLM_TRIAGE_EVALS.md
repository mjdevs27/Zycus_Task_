# Claude Code Fix Prompt — Streamlit LLM Config, Triage Crash, and Eval Errors

## Context

You are Claude Code working inside my **US Delivery AI Support Tools** project.

This project is for the **US Delivery Internship Technical Task Round**.

The assignment requires:

```txt
Task 1 — Intelligent ticket triage agent
Task 2 — TAM account health summariser
Task 3 — Evaluation harness
Task 4 — Design note
Bonus — Streamlit UI, streaming output, CI, prompt versioning
```

The official starter repo is supposed to provide:

```txt
500 synthetic support tickets
50 synthetic customer account summaries
Markdown knowledge-base docs
```

But currently the official dataset may be missing or empty.

The project must remain dataset-ready, not dataset-fabricated.

---

## Current Problems

I am facing these issues in Streamlit:

### Problem 1 — LLM config is not loading

The Streamlit sidebar shows:

```txt
OpenAI default endpoint · model gpt-4o-mini
LLM API key: not configured
```

But my local `.env` is supposed to configure Groq through OpenAI-compatible API:

```env
OPENAI_API_KEY=local_real_key_only_in_env
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_MODEL=llama-3.3-70b-versatile
LLM_TEMPERATURE=0
LLM_SEED=42
```

Expected Streamlit sidebar:

```txt
Groq OpenAI-compatible endpoint · model llama-3.3-70b-versatile
LLM API key: configured
```

Do not display the actual key.

---

### Problem 2 — Ticket triage crashes

When I click **Run triage** in Streamlit, it shows:

```txt
An unexpected error occurred while triaging the ticket.
```

The ticket input was:

```txt
Subject:
SSO login outage after SAML configuration update

Body:
All users are unable to log in after we changed the SAML configuration this morning. This is blocking production access for the customer’s team, and they need urgent support to restore access.
```

Task 1 should work even if official dataset is missing because the user provides a new incoming ticket directly.

If KB docs are missing, triage must not hallucinate a known issue match.

If LLM is unavailable, triage must return a deterministic local fallback response instead of crashing.

---

### Problem 3 — Evals are failing

The eval harness should not crash when official dataset is missing.

Expected:

```bash
python -m evals.run_evals
```

must:

```txt
Generate eval_report.json
Generate eval_report.md
Include dataset_ready=false if official data is missing
Run triage cases using direct ticket input/fallback
Mark account-summary cases requiring official dataset as failed gracefully with clear notes
Never invent account data
Never create fake official tickets/accounts/KB
```

---

## Non-Negotiable Rules

Do not:

```txt
Create fake official tickets
Create fake official accounts
Create fake official KB docs
Scrape external data
Use real customer data
Commit `.env`
Print or log the real API key
Hardcode my Groq key anywhere
Put real keys into `.env.example`
Make evals pass by inventing dataset content
Let Task 1 crash because official dataset/KB is missing
```

`.env` is local only and must remain Git-ignored.

`.env.example` must contain placeholders only.

---

## Files to Inspect First

Before editing, inspect:

```txt
ui/streamlit_app.py
app/config.py
app/llm_client.py
app/triage_agent.py
app/schemas.py
app/retrieval.py
app/kb_loader.py
app/data_loader.py
evals/run_evals.py
evals/scoring.py
evals/report.py
evals/test_cases/triage_tests.json
evals/test_cases/account_summary_tests.json
.env.example
.gitignore
requirements.txt
```

Then implement the fixes below.

---

# Part 1 — Fix Streamlit Environment Loading

Open:

```txt
ui/streamlit_app.py
```

At the very top of the file, before importing any `app.*` modules, add or correct this bootstrap block:

```python
from pathlib import Path
import sys
import os

import streamlit as st
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env", override=False)

try:
    for key, value in st.secrets.items():
        os.environ.setdefault(key, str(value))
except Exception:
    pass
```

Important:

```txt
This block must execute before importing app.config or any app module that reads settings.
Do not display the API key.
Do not require Streamlit secrets locally.
```

After this block, import project modules:

```python
from app.config import settings
from app.schemas import TicketTriageRequest
from app.triage_agent import TicketTriageAgent
from app.account_summarizer import AccountHealthSummarizer
from app.data_loader import check_dataset_status
```

---

# Part 2 — Fix Config Loading

Open:

```txt
app/config.py
```

Make sure config reads from:

```txt
normal environment variables
local .env
Streamlit secrets bridged into os.environ
```

If using `pydantic-settings`, the settings class should support env names like:

```env
OPENAI_API_KEY
OPENAI_BASE_URL
OPENAI_MODEL
LLM_TEMPERATURE
LLM_SEED
```

A correct structure can look like:

```python
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[1]

class Settings(BaseSettings):
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-4o-mini"

    llm_temperature: float = 0
    llm_seed: int = 42

    data_dir: str = "./data"
    tickets_file: str = "./data/tickets.json"
    accounts_file: str = "./data/accounts.json"
    kb_dir: str = "./knowledge-base"

    prompt_dir: str = "./prompts"
    triage_prompt_version: str = "triage_v1"
    account_prompt_version: str = "account_summary_v1"
    judge_prompt_version: str = "judge_v1"

    top_k_kb_docs: int = 3

    eval_report_json: str = "./eval_report.json"
    eval_report_md: str = "./eval_report.md"

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()

def is_llm_configured() -> bool:
    return bool(settings.openai_api_key)
```

If the project already has a settings class, do not rewrite unnecessarily. Fix it so:

```txt
settings.openai_api_key loads OPENAI_API_KEY
settings.openai_base_url loads OPENAI_BASE_URL
settings.openai_model loads OPENAI_MODEL
settings.llm_temperature loads LLM_TEMPERATURE
settings.llm_seed loads LLM_SEED
```

Do not print the key.

---

# Part 3 — Fix Streamlit Sidebar Display

In:

```txt
ui/streamlit_app.py
```

Update the sidebar model/provider display.

Expected behavior:

If `.env` has Groq config:

```txt
Groq OpenAI-compatible endpoint · model llama-3.3-70b-versatile
LLM API key: configured
```

If no key:

```txt
LLM API key: not configured
```

Suggested code:

```python
from app.config import settings

provider_label = "OpenAI default endpoint"

if settings.openai_base_url:
    if "groq" in settings.openai_base_url.lower():
        provider_label = "Groq OpenAI-compatible endpoint"
    else:
        provider_label = "OpenAI-compatible endpoint"

st.sidebar.write(f"{provider_label} · model `{settings.openai_model}`")
st.sidebar.write("LLM API key: configured" if settings.openai_api_key else "LLM API key: not configured")
```

Do not show the key value.

---

# Part 4 — Fix LLM Client for Groq OpenAI-Compatible API

Open:

```txt
app/llm_client.py
```

The LLM client must use:

```txt
settings.openai_api_key
settings.openai_base_url
settings.openai_model
settings.llm_temperature
settings.llm_seed
```

Make sure the OpenAI-compatible client uses `base_url`:

```python
from openai import OpenAI

client = OpenAI(
    api_key=self.api_key,
    base_url=self.base_url if self.base_url else None,
)
```

Required behavior for `complete_json()`:

```txt
Raise MissingLLMConfigurationError if no key.
Try JSON response format if supported.
If provider rejects response_format, retry without response_format.
Strip Markdown JSON fences.
Extract JSON object from text.
Parse JSON.
Raise LLMJSONParseError if invalid.
Do not print raw prompts.
Do not print keys.
```

Groq can be used through the OpenAI-compatible endpoint, so the code must not force OpenAI default endpoint when `OPENAI_BASE_URL` is provided.

---

# Part 5 — Fix Triage So It Never Crashes for Missing Dataset/KB/LLM

Open:

```txt
app/triage_agent.py
```

Task 1 must work even if official dataset is missing because the user provides a new incoming ticket directly.

Fix `TicketTriageAgent.triage()` so:

```txt
Missing official tickets/accounts does not affect triage.
Missing KB docs does not crash triage.
Missing LLM key does not crash triage.
Invalid LLM JSON does not crash triage.
Controlled failures return a valid fallback TicketTriageResponse.
```

Expected behavior if KB docs are missing:

```json
{
  "known_issue_match": {
    "matched": false,
    "doc_title": null,
    "doc_path": null,
    "match_reason": "No knowledge-base documents were available for retrieval.",
    "confidence": 0.0
  }
}
```

Fallback urgency rules:

```txt
P1: outage, all users, production down, data loss, security, blocked production access
P2: broken, blocked, urgent, major customer/account impact
P3: normal issue, limited scope, workaround likely
P4: documentation, how-to, minor question
```

For this ticket:

```txt
SSO login outage after SAML configuration update
All users are unable to log in after we changed the SAML configuration this morning. This is blocking production access for the customer’s team, and they need urgent support to restore access.
```

Fallback should produce:

```txt
product_area: authentication or identity/access
issue_category: login/sso
urgency_tier: P1
recommended_team: Authentication / Identity Support
draft_first_response: professional support response
```

Do not depend on KB for this.

Do not require official dataset for this.

---

# Part 6 — Fix Streamlit Triage Error Display

Currently Streamlit hides the real error.

In `ui/streamlit_app.py`, replace broad hidden exception handling with:

```python
except Exception as e:
    st.error("An unexpected error occurred while triaging the ticket.")
    with st.expander("Debug details"):
        st.exception(e)
```

This is allowed during development.

For final submission, keep debug details inside an expander or show only when:

```python
settings.app_env == "development"
```

If fallback is fixed correctly, this block should rarely run.

---

# Part 7 — Add Direct Triage Smoke Test Script

Create:

```txt
scripts/smoke_test_triage.py
```

Behavior:

```txt
Load .env.
Instantiate TicketTriageAgent.
Send the SSO outage ticket.
Print response JSON.
Exit 0 if urgency_tier and draft_first_response exist.
Exit 1 otherwise.
Do not print API key.
```

Suggested implementation shape:

```python
from pathlib import Path
import sys
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
load_dotenv(ROOT_DIR / ".env")

from app.schemas import TicketTriageRequest
from app.triage_agent import TicketTriageAgent

def main():
    req = TicketTriageRequest(
        subject="SSO login outage after SAML configuration update",
        body="All users are unable to log in after we changed the SAML configuration this morning. This is blocking production access for the customer’s team, and they need urgent support to restore access.",
    )

    result = TicketTriageAgent().triage(req)

    if hasattr(result, "model_dump"):
        data = result.model_dump()
    elif hasattr(result, "dict"):
        data = result.dict()
    else:
        data = result

    print(data)

    if not data.get("urgency_tier") or not data.get("draft_first_response"):
        raise SystemExit(1)

if __name__ == "__main__":
    main()
```

Adjust field names if the schema differs.

---

# Part 8 — Fix Evals So They Do Not Crash Without Official Data

Open:

```txt
evals/run_evals.py
evals/scoring.py
evals/report.py
evals/test_cases/triage_tests.json
evals/test_cases/account_summary_tests.json
```

Required command:

```bash
python -m evals.run_evals
```

must:

```txt
Load triage and account eval cases.
Run triage cases.
Handle account cases requiring official dataset gracefully.
Generate eval_report.json.
Generate eval_report.md.
Include dataset_ready true/false.
Never invent account data.
Never create fake official dataset.
```

If dataset is missing:

```txt
Triage cases should still run with direct ticket input/fallback.
Account-summary cases with requires_official_dataset=true should return failed EvalCaseResult with score 0.
The notes must explain the official dataset is not ready.
```

Use this note:

```txt
Official dataset is not ready, so this account-summary case could not be executed without inventing account data.
```

Do not mark those account cases as passed.

Do not generate fake account summaries.

---

# Part 9 — Fix Eval Report Writing

Ensure `evals/report.py` writes:

```txt
eval_report.json
eval_report.md
```

Both should be valid even when dataset is missing.

Markdown report must include:

```txt
Dataset ready: false
Total cases
Passed
Failed
Average score
Table of results
Notes explaining dataset-dependent account failures
```

JSON report must include:

```txt
generated_at
dataset_ready
total_cases
passed_cases
failed_cases
average_score
results
```

---

# Part 10 — Commands to Run After Fixes

Run:

```bash
python scripts/smoke_test_triage.py
```

Then:

```bash
pytest tests/test_pii.py tests/test_triage_agent.py tests/test_api.py
```

Then:

```bash
python -m evals.run_evals
```

Then:

```bash
python -m compileall app evals tests ui scripts
```

Then:

```bash
streamlit run ui/streamlit_app.py
```

In the UI, verify:

```txt
Sidebar shows Groq OpenAI-compatible endpoint.
Sidebar shows model llama-3.3-70b-versatile.
Sidebar shows LLM API key configured.
Ticket triage no longer crashes.
Eval runner creates reports.
```

---

# Part 11 — Secret Safety Check

Run:

```bash
git check-ignore -v .env
git ls-files .env
```

Expected:

```txt
.env is ignored
git ls-files .env prints nothing
```

Run:

```bash
python scripts/check_secrets.py
```

If the scanner flags `.env`, adjust scanner logic so it ignores local `.env` only if `.env` is untracked and ignored.

It must still scan:

```txt
.env.example
source code
README
workflow files
prompts
docs
```

Do not weaken scanner to allow committed secrets.

---

# Final Acceptance Criteria

The fix is complete only when all are true:

```txt
[ ] Streamlit sidebar shows Groq/OpenAI-compatible endpoint when .env has OPENAI_BASE_URL.
[ ] Streamlit sidebar shows model llama-3.3-70b-versatile from .env.
[ ] Streamlit sidebar shows LLM API key configured without showing the key.
[ ] Ticket triage button no longer shows unexpected error.
[ ] Ticket triage works even if official dataset is missing.
[ ] Missing KB does not crash triage.
[ ] Missing KB forces known_issue_match.matched=false.
[ ] If LLM is unavailable, fallback triage returns valid response.
[ ] python -m evals.run_evals does not crash.
[ ] eval_report.json and eval_report.md are generated.
[ ] Missing official dataset is reported honestly as dataset_ready=false.
[ ] No fake official data was created.
[ ] .env is ignored and untracked.
[ ] No real secret is committed or printed.
```

Implement these fixes now.
