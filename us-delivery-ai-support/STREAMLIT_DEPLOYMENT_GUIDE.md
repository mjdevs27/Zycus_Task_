# Streamlit Community Cloud Deployment Guide

## Purpose

Use this guide to deploy the US Delivery AI Support Tools project on **Streamlit Community Cloud** and obtain a public Streamlit URL.

Your Streamlit entry file is expected to be:

```txt
ui/streamlit_app.py
```

This deployment is for the Streamlit UI only. It should let you demo:

```txt
Dataset status
Task 1 ticket triage
Task 2 TAM account brief when official data exists
Eval report display
```

The official dataset may still be missing or empty. That is acceptable only if the app clearly shows `dataset_ready=false` and does not fabricate tickets, accounts, or knowledge-base docs.

---

## Critical Rules Before Deployment

Do not deploy or commit:

```txt
.env
real API keys
real Groq/OpenAI keys
fake official tickets
fake official accounts
fake official knowledge-base docs
real customer data
```

The assessment says the solution must use the provided mock dataset exclusively and must not introduce external data. It also treats committed credentials as an automatic disqualifier.

So the deployed app must be honest:

```txt
Ticket triage can work with direct user input.
Account brief requires official accounts.json and tickets.json.
Known issue matching requires official knowledge-base Markdown docs.
If those files are missing, show a clear warning.
```

---

## Step 1 — Confirm Project Structure

From the project root, run:

```bash
ls
```

You should have:

```txt
app/
data/
evals/
knowledge-base/
prompts/
tests/
ui/
requirements.txt
.env.example
.gitignore
README.md
run.py
```

Your Streamlit app must exist here:

```txt
ui/streamlit_app.py
```

If this file does not exist, run the Streamlit UI implementation MD first.

---

## Step 2 — Fix Streamlit Import Path

Because `streamlit_app.py` is inside `ui/`, it may fail to import `app.*` on Streamlit Cloud.

At the very top of `ui/streamlit_app.py`, before importing project modules, add:

```python
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
```

Then your imports can work:

```python
from app.data_loader import check_dataset_status
from app.schemas import TicketTriageRequest
from app.triage_agent import TicketTriageAgent
from app.account_summarizer import AccountHealthSummarizer
```

---

## Step 3 — Add Streamlit Secrets Bridge

Your local `.env` is not deployed to Streamlit Cloud. On Streamlit Cloud, secrets are added from the app settings.

At the top of `ui/streamlit_app.py`, after importing `os` and `streamlit`, add:

```python
import os
import streamlit as st

try:
    for key, value in st.secrets.items():
        os.environ.setdefault(key, str(value))
except Exception:
    pass
```

Place this before importing modules that load config.

Recommended final top section:

```python
from pathlib import Path
import sys
import os
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    for key, value in st.secrets.items():
        os.environ.setdefault(key, str(value))
except Exception:
    pass

from app.data_loader import check_dataset_status
from app.schemas import TicketTriageRequest
from app.triage_agent import TicketTriageAgent
from app.account_summarizer import AccountHealthSummarizer
```

This allows the same config code to work locally with `.env` and on Streamlit Cloud with secrets.

---

## Step 4 — Verify `requirements.txt`

Streamlit Community Cloud installs Python dependencies from a dependency file. Use `requirements.txt` in the repo root.

Your `requirements.txt` should contain at least:

```txt
streamlit
fastapi
uvicorn
pydantic
pydantic-settings
python-dotenv
openai
numpy
scikit-learn
pytest
httpx
```

Do not put commands inside `requirements.txt`.

Wrong:

```txt
pip install streamlit
```

Correct:

```txt
streamlit
```

---

## Step 5 — Confirm `.gitignore`

Your `.gitignore` must include:

```gitignore
.env
*.env
.env.local
.venv/
venv/
__pycache__/
.pytest_cache/
```

Do not ignore `.env.example`.

Check:

```bash
git check-ignore -v .env
```

Expected:
- It should show a `.gitignore` rule.

Check if `.env` is tracked:

```bash
git ls-files .env
```

Expected:
- It should print nothing.

If it prints `.env`, run:

```bash
git rm --cached .env
```

---

## Step 6 — Rotate Any Exposed Groq Key

If a Groq key was pasted into terminal/chat/logs earlier, rotate it before deployment.

Do this manually:

```txt
Groq Console → API Keys → Delete/Revoke old key → Create new key
```

Use only the new key.

Do not put the new key in:

```txt
README.md
.env.example
GitHub Actions YAML
source code
commit history
terminal screenshots
Loom video
```

Put it only in:

```txt
local .env
Streamlit Cloud secrets
```

---

## Step 7 — Test Locally

Run:

```bash
streamlit run ui/streamlit_app.py
```

Open:

```txt
http://localhost:8501
```

Test these sections:

```txt
Dataset Status
Ticket Triage
TAM Account Brief
Eval Report
```

Expected if official data is missing:

```txt
Dataset Status: ready=false
Ticket Triage: should still work using direct ticket input
TAM Account Brief: should show missing dataset/account warning
Eval Report: may show dataset_ready=false
```

Test ticket triage with:

```txt
Subject:
SSO login outage after SAML update

Body:
All users are unable to log in after we changed the SAML configuration this morning. This is blocking production access for our team.
```

Expected:

```txt
urgency_tier present
reasoning present
recommended_team present
draft_first_response present
known_issue_match false if KB docs are unavailable
```

---

## Step 8 — Run Safety Checks Before Commit

Run:

```bash
python scripts/check_secrets.py
```

If `scripts/check_secrets.py` does not exist, at minimum run:

```bash
git status
git check-ignore -v .env
git ls-files .env
```

Expected:

```txt
.env ignored
.env not tracked
.env.example safe
no real keys in staged files
```

Then run tests:

```bash
pytest
python -m compileall app evals tests ui
```

Run eval harness:

```bash
python -m evals.run_evals
```

If official data is missing, the eval report should still generate with:

```txt
dataset_ready=false
```

That is acceptable.

---

## Step 9 — Commit and Push to GitHub

Check status:

```bash
git status
```

Add files:

```bash
git add .
```

Check again:

```bash
git status
```

Make sure `.env` is not listed.

Commit:

```bash
git commit -m "Prepare Streamlit deployment"
```

Push to GitHub:

```bash
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git push -u origin main
```

If remote already exists:

```bash
git push origin main
```

---

## Step 10 — Create App on Streamlit Community Cloud

Open:

```txt
https://share.streamlit.io/
```

or go through your Streamlit Community Cloud dashboard.

Deploy flow:

```txt
1. Sign in with GitHub.
2. Click New app / Create app.
3. Select your GitHub repository.
4. Select branch: main.
5. Set app entrypoint/main file path: ui/streamlit_app.py.
6. Open Advanced settings.
7. Select Python version 3.11 if available.
8. Paste secrets in TOML format.
9. Click Deploy.
```

Streamlit Community Cloud apps are deployed from GitHub by selecting the repository, branch, and entrypoint file. Apps deploy to a `streamlit.app` subdomain, and you can set the app URL/subdomain during deployment if available.

---

## Step 11 — Add Streamlit Secrets

In the Streamlit deployment advanced settings or app settings, paste secrets in TOML format.

Use this template:

```toml
OPENAI_API_KEY = "your_new_rotated_groq_key_here"
OPENAI_BASE_URL = "https://api.groq.com/openai/v1"
OPENAI_MODEL = "llama-3.3-70b-versatile"

LLM_TEMPERATURE = "0"
LLM_SEED = "42"

APP_ENV = "production"
APP_HOST = "0.0.0.0"
APP_PORT = "8000"

DATA_DIR = "./data"
TICKETS_FILE = "./data/tickets.json"
ACCOUNTS_FILE = "./data/accounts.json"
KB_DIR = "./knowledge-base"

PROMPT_DIR = "./prompts"
TRIAGE_PROMPT_VERSION = "triage_v1"
ACCOUNT_PROMPT_VERSION = "account_summary_v1"
JUDGE_PROMPT_VERSION = "judge_v1"

TOP_K_KB_DOCS = "3"

EVAL_REPORT_JSON = "./eval_report.json"
EVAL_REPORT_MD = "./eval_report.md"
```

Important:

```txt
Do not add quotes around the TOML block itself.
Do not paste this into GitHub.
Do not commit .streamlit/secrets.toml.
```

Streamlit Cloud stores secrets through the app settings. Locally, Streamlit can use `.streamlit/secrets.toml`, but that file should not be committed.

---

## Step 12 — Wait for Deployment

Streamlit Cloud will install dependencies and build the app.

If successful, you will get a public URL like:

```txt
https://your-app-name.streamlit.app
```

That is your deployment URL.

Save it for:

```txt
README
submission form
Loom demo
```

---

## Step 13 — Test the Deployed App

Open your Streamlit URL.

Test:

```txt
Dataset Status
Ticket Triage
Eval Report
```

Use the ticket triage input:

```txt
Subject:
SSO login outage after SAML update

Body:
All users are unable to log in after we changed the SAML configuration this morning. This is blocking production access for our team.
```

Expected:

```txt
Structured triage output appears.
Urgency tier appears.
Recommended team appears.
Draft first response appears.
If KB is missing, known issue match is false.
```

If the official data is missing, Account Brief should not invent account details. It should show a clear missing dataset/account warning.

---

## Step 14 — Common Deployment Errors and Fixes

### Error: `ModuleNotFoundError: No module named 'app'`

Fix:

```python
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
```

Put this at the top of `ui/streamlit_app.py`.

---

### Error: missing dependencies

Fix `requirements.txt`.

Then push again:

```bash
git add requirements.txt
git commit -m "Fix deployment dependencies"
git push origin main
```

Streamlit will redeploy.

---

### Error: API key missing

Add secrets in Streamlit Cloud settings.

Make sure your app bridges `st.secrets` to `os.environ`.

---

### Error: app crashes because dataset missing

Fix the UI to catch dataset errors.

Expected behavior:

```txt
Show warning.
Do not crash.
Do not create fake data.
```

---

### Error: account brief does not work

If official data is missing, this is expected.

It should show:

```txt
Dataset not ready
Account data unavailable
Replace placeholder account ID after official dataset is provided
```

It should not hallucinate a customer brief.

---

### Error: `OPENAI_BASE_URL` not being used

Check `app/llm_client.py`.

It should initialize OpenAI-compatible client with base URL when provided.

Expected shape:

```python
client = OpenAI(
    api_key=api_key,
    base_url=base_url or None
)
```

---

## Step 15 — If Official Dataset Arrives Later

If the official dataset is allowed to be committed:

```txt
data/tickets.json
data/accounts.json
knowledge-base/**/*.md
```

Then:

```bash
git add data/tickets.json data/accounts.json knowledge-base/
git commit -m "Add official assessment mock dataset"
git push origin main
```

Streamlit will redeploy automatically.

If the official dataset is confidential and should not be public:
- Do not commit it to a public repo.
- Keep deployment code-only.
- Show dataset readiness as false.
- Use local demo with official dataset for Loom if permitted.

---

## Step 16 — Final Deployment Checklist

Before sharing the URL:

```txt
[ ] Exposed Groq key rotated
[ ] .env ignored
[ ] .env not tracked
[ ] .env.example contains placeholders only
[ ] requirements.txt exists in repo root
[ ] ui/streamlit_app.py exists
[ ] app import path fixed in streamlit_app.py
[ ] Streamlit secrets added
[ ] Local streamlit run works
[ ] Repo pushed to GitHub
[ ] Streamlit app entrypoint set to ui/streamlit_app.py
[ ] Deployed URL opens
[ ] Ticket triage works on deployed app
[ ] Missing official dataset handled honestly
[ ] No fake tickets/accounts/KB added
```

---

## Final URL Format

After successful deployment, your app URL will look like:

```txt
https://your-selected-app-name.streamlit.app
```

This is the URL you submit or put in your README/Loom notes.
