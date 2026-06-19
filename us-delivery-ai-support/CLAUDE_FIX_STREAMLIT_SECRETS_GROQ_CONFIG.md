# Claude Code Prompt — Fix Streamlit Secrets, Groq Config, and Triage Fallback

## Context

You are Claude Code working inside my **US Delivery AI Support Tools** Streamlit project.

The project is for the **US Delivery Internship Technical Task Round**.

The app has:

```txt
Task 1 — Ticket triage
Task 2 — TAM account health summariser
Task 3 — Evaluation harness
Task 4 — Design note
Bonus — Streamlit UI, streaming, CI, prompt versioning
```

The Streamlit UI is deployed or being tested, but the sidebar still shows:

```txt
OpenAI default endpoint · model gpt-4o-mini
LLM API key: not configured
```

However, I already added both local `.env` and Streamlit Cloud Secrets with Groq/OpenAI-compatible configuration:

```toml
OPENAI_API_KEY = "my_new_groq_key"
OPENAI_BASE_URL = "https://api.groq.com/openai/v1"
OPENAI_MODEL = "llama-3.3-70b-versatile"
LLM_TEMPERATURE = "0"
LLM_SEED = "42"
```

This means one of these is broken:

```txt
1. ui/streamlit_app.py is importing app.config before loading Streamlit secrets.
2. app/config.py is not mapping env variables correctly.
3. app/llm_client.py is ignoring OPENAI_BASE_URL.
4. Streamlit is reading stale/default config values.
5. Ticket triage is crashing instead of using fallback.
```

Fix this completely.

---

## Strict Rules

Do not:

```txt
Print or expose the actual API key.
Commit .env.
Put real secrets into .env.example.
Create fake official tickets.
Create fake official accounts.
Create fake official KB docs.
Use external data.
Break missing-dataset behavior.
Make evals pass by inventing data.
```

Task 1 ticket triage must work even if:

```txt
official dataset is missing
knowledge-base docs are missing
LLM key is missing
LLM returns invalid JSON
```

If the LLM is unavailable, triage must use deterministic fallback instead of crashing.

---

## Files to Inspect First

Inspect these files before editing:

```txt
ui/streamlit_app.py
app/config.py
app/llm_client.py
app/triage_agent.py
app/schemas.py
.env.example
.gitignore
requirements.txt
```

Then implement the tasks below.

---

# Task 1 — Fix Streamlit Import Order

Open:

```txt
ui/streamlit_app.py
```

At the absolute top of the file, before **any** `app.*` import, place this exact bootstrap block:

```python
from pathlib import Path
import sys
import os

import streamlit as st
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Local development: load project-root .env
load_dotenv(ROOT_DIR / ".env", override=False)

# Streamlit Cloud: copy secrets into environment variables BEFORE app.config imports
try:
    for key, value in st.secrets.items():
        os.environ[str(key)] = str(value)
except Exception:
    pass
```

Important:

```txt
This block must be the first project-related code in the file.
It must run before `from app.config import settings`.
It must run before importing TicketTriageAgent, AccountHealthSummarizer, data_loader, etc.
Use os.environ[str(key)] = str(value), not setdefault.
Do not print the API key.
```

After this bootstrap block, import app modules:

```python
from app.config import settings
from app.data_loader import check_dataset_status
from app.schemas import TicketTriageRequest
from app.triage_agent import TicketTriageAgent
from app.account_summarizer import AccountHealthSummarizer
```

Also search the whole file and make sure there are no `app.*` imports above the bootstrap block.

---

# Task 2 — Fix app/config.py Env Variable Mapping

Open:

```txt
app/config.py
```

Make sure the Settings class correctly maps these env vars:

```txt
OPENAI_API_KEY -> settings.openai_api_key
OPENAI_BASE_URL -> settings.openai_base_url
OPENAI_MODEL -> settings.openai_model
LLM_TEMPERATURE -> settings.llm_temperature
LLM_SEED -> settings.llm_seed
```

Use this robust config structure if the current one is wrong:

```python
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[1]

class Settings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str | None = Field(default=None, alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    llm_temperature: float = Field(default=0, alias="LLM_TEMPERATURE")
    llm_seed: int = Field(default=42, alias="LLM_SEED")

    data_dir: str = Field(default="./data", alias="DATA_DIR")
    tickets_file: str = Field(default="./data/tickets.json", alias="TICKETS_FILE")
    accounts_file: str = Field(default="./data/accounts.json", alias="ACCOUNTS_FILE")
    kb_dir: str = Field(default="./knowledge-base", alias="KB_DIR")

    prompt_dir: str = Field(default="./prompts", alias="PROMPT_DIR")
    triage_prompt_version: str = Field(default="triage_v1", alias="TRIAGE_PROMPT_VERSION")
    account_prompt_version: str = Field(default="account_summary_v1", alias="ACCOUNT_PROMPT_VERSION")
    judge_prompt_version: str = Field(default="judge_v1", alias="JUDGE_PROMPT_VERSION")

    top_k_kb_docs: int = Field(default=3, alias="TOP_K_KB_DOCS")

    eval_report_json: str = Field(default="./eval_report.json", alias="EVAL_REPORT_JSON")
    eval_report_md: str = Field(default="./eval_report.md", alias="EVAL_REPORT_MD")

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

settings = Settings()

def is_llm_configured() -> bool:
    return bool(settings.openai_api_key)
```

If a similar class already exists, do not rewrite unnecessarily. Just make sure aliases and defaults are correct.

Do not print:

```txt
settings.openai_api_key
```

---

# Task 3 — Fix Streamlit Sidebar Display

In:

```txt
ui/streamlit_app.py
```

Update sidebar display.

Use this logic:

```python
provider_label = "OpenAI default endpoint"

if settings.openai_base_url:
    if "groq" in settings.openai_base_url.lower():
        provider_label = "Groq OpenAI-compatible endpoint"
    else:
        provider_label = "OpenAI-compatible endpoint"

st.sidebar.markdown("### Model / provider")
st.sidebar.write(f"{provider_label} · model `{settings.openai_model}`")
st.sidebar.write("LLM API key: configured" if settings.openai_api_key else "LLM API key: not configured")
```

Expected output after fix:

```txt
Groq OpenAI-compatible endpoint · model llama-3.3-70b-versatile
LLM API key: configured
```

Add a safe debug expander:

```python
with st.sidebar.expander("Config debug", expanded=False):
    st.write("OPENAI_API_KEY loaded:", bool(settings.openai_api_key))
    st.write("OPENAI_BASE_URL loaded:", bool(settings.openai_base_url))
    st.write("OPENAI_MODEL:", settings.openai_model)
    st.write("APP_ENV:", settings.app_env)
```

Do not print the actual key.

---

# Task 4 — Verify Streamlit Secrets Format

Streamlit Secrets must be root-level TOML keys like this:

```toml
OPENAI_API_KEY = "real_key_goes_here"
OPENAI_BASE_URL = "https://api.groq.com/openai/v1"
OPENAI_MODEL = "llama-3.3-70b-versatile"
LLM_TEMPERATURE = "0"
LLM_SEED = "42"
```

Do not use `.env` format in Streamlit Secrets.

Wrong:

```txt
OPENAI_API_KEY=...
```

Correct:

```toml
OPENAI_API_KEY = "..."
```

If secrets are nested under a section like `[llm]`, either remove nesting or update code to flatten nested secrets. Prefer root-level keys.

---

# Task 5 — Fix LLM Client to Use Groq Base URL

Open:

```txt
app/llm_client.py
```

Make sure the OpenAI client is initialized with `base_url`:

```python
from openai import OpenAI

client = OpenAI(
    api_key=self.api_key,
    base_url=self.base_url if self.base_url else None,
)
```

The LLM client must use:

```txt
settings.openai_api_key
settings.openai_base_url
settings.openai_model
settings.llm_temperature
settings.llm_seed
```

If no key exists:

```txt
Do not fail during app import.
Raise MissingLLMConfigurationError only when making an LLM call.
```

For `complete_json()`:

```txt
Try response_format={"type": "json_object"} if supported.
If provider rejects response_format, retry without it.
Strip markdown fences.
Extract JSON object.
Parse JSON.
Do not log prompt/key.
```

---

# Task 6 — Make Triage Fallback Safe

Open:

```txt
app/triage_agent.py
```

Ticket triage must not crash if:

```txt
official dataset is missing
KB docs are missing
LLM key is missing
LLM returns invalid JSON
```

Required behavior:

```txt
Missing KB -> retrieved_docs=[]
Missing KB -> known_issue_match.matched=false
Missing LLM -> deterministic fallback response
Invalid LLM JSON -> deterministic fallback response
```

Fallback urgency rules:

```txt
P1: outage, all users, production down, data loss, security, blocked production access
P2: broken, blocked, urgent, major customer/account impact
P3: normal issue, limited scope
P4: documentation, how-to, minor question
```

For this ticket:

```txt
Subject:
SSO login outage after SAML configuration update

Body:
All users are unable to log in after we changed the SAML configuration this morning. This is blocking production access for the customer’s team, and they need urgent support to restore access.
```

Fallback should return:

```txt
product_area: authentication or identity/access
issue_category: login/sso
urgency_tier: P1
recommended_team: Authentication / Identity Support
draft_first_response present
known_issue_match.matched=false if no KB docs
```

---

# Task 7 — Add Local Config Smoke Test

Create:

```txt
scripts/smoke_test_config.py
```

It should:

```python
from pathlib import Path
import sys
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
load_dotenv(ROOT_DIR / ".env", override=False)

from app.config import settings

print("OPENAI_API_KEY loaded:", bool(settings.openai_api_key))
print("OPENAI_BASE_URL loaded:", bool(settings.openai_base_url))
print("OPENAI_MODEL:", settings.openai_model)
print("APP_ENV:", settings.app_env)

if not settings.openai_model:
    raise SystemExit(1)
```

Do not print actual API key.

Run:

```bash
python scripts/smoke_test_config.py
```

Expected locally if `.env` is configured:

```txt
OPENAI_API_KEY loaded: True
OPENAI_BASE_URL loaded: True
OPENAI_MODEL: llama-3.3-70b-versatile
```

---

# Task 8 — Run Checks

Run:

```bash
python scripts/smoke_test_config.py
python -m compileall app ui scripts tests
pytest tests/test_triage_agent.py tests/test_api.py
streamlit run ui/streamlit_app.py
```

In local Streamlit, verify:

```txt
sidebar shows Groq OpenAI-compatible endpoint
model shows llama-3.3-70b-versatile
LLM API key shows configured
ticket triage works
```

---

# Task 9 — Deployment Check

After fixing:

```bash
git status
git check-ignore -v .env
git ls-files .env
```

Expected:

```txt
.env ignored
git ls-files .env prints nothing
```

Then commit and push code changes, not `.env`:

```bash
git add ui/streamlit_app.py app/config.py app/llm_client.py app/triage_agent.py scripts/smoke_test_config.py
git status
git commit -m "Fix Streamlit secret loading and Groq config"
git push origin main
```

Then in Streamlit Cloud:

```txt
Confirm secrets are saved in TOML.
Reboot/redeploy the app.
Verify sidebar again.
```

---

# Final Acceptance Criteria

The fix is complete only when:

```txt
[ ] Streamlit no longer shows gpt-4o-mini when Groq secrets are present.
[ ] Streamlit shows llama-3.3-70b-versatile.
[ ] Streamlit shows LLM API key configured.
[ ] Ticket triage works.
[ ] No real key is printed.
[ ] .env remains untracked.
```

## Why This Is Happening

The app is likely creating:

```python
settings = Settings()
```

before Streamlit secrets are injected into:

```python
os.environ
```

So the settings object falls back to defaults:

```txt
gpt-4o-mini
no API key
no Groq base URL
```

This prompt fixes the load order and config mapping.
