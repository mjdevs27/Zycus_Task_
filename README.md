# Zycus Support AI

AI-powered support triage and TAM account health summariser for the **US Delivery Internship / Zycus Engineering Assessment**.

This project implements production-style internal tooling for two customer-facing teams:

- **Technical Support** — triages incoming support tickets, assigns urgency, routes to the right team, and drafts the first response.
- **Technical Account Management** — generates account health briefs from account summaries and recent support tickets when the official dataset is available.

The implementation is designed to be **safe, deterministic where required, dataset-aware, and honest about missing official data**. It never fabricates support tickets, account records, or knowledge-base documents.

---

## 🎬 Walkthrough Video

▶️ **Click here to watch the walkthrough:** `https://www.loom.com/share/ba74853feee24171871add67fb4c4682`

---

## 🚀 Live App

🌐 **Open Streamlit App:**  
https://zycustask-gtwa2frvp5zebf3djbn3m6.streamlit.app/

---

## Assessment Mapping

| Assessment Task | Requirement | Implementation |
|---|---|---|
| **Task 1 — Intelligent Ticket Triage Agent** | Accept raw ticket text or subject/body, classify product area, issue category, urgency P1–P4, identify KB match, recommend responder team, draft first response | `app/triage_agent.py`, `app/retrieval.py`, `app/kb_loader.py`, `POST /triage`, Streamlit Ticket Triage tab |
| **Task 2 — TAM Account Health Summariser** | Accept account ID, pull account summary and last 90 days of tickets, generate executive summary, risks, talking points, justify risks with direct ticket quotes | `app/account_summarizer.py`, `POST /accounts/{account_id}/brief`, Streamlit Account Brief tab |
| **Task 3 — Evaluation Harness** | At least 5 test cases per task, pass/fail, quality score 0–1, JSON/Markdown summary report, adversarial cases | `evals/run_evals.py`, `evals/scoring.py`, `evals/report.py`, `evals/test_cases/`, `eval_report.json`, `eval_report.md`, Streamlit Eval Report tab |
| **Task 4 — Design Note** | Failure modes, latency vs quality, data sensitivity, scaling to 10× ticket volume | `DESIGN_NOTE.md` and summary section in this README |
| **Bonus — Thin UI** | Streamlit demo for non-technical users | `ui/streamlit_app.py` |
| **Bonus — Streaming Output** | Streaming demonstrated for Task 1 or Task 2 | `app/streaming.py`, `/accounts/{account_id}/brief/stream` if enabled |
| **Bonus — CI** | GitHub Actions runs eval harness on every commit | `.github/workflows/evals.yml` |
| **Bonus — Prompt Versioning** | Prompts tracked with version IDs and changelog | `prompts/triage_v1.md`, `prompts/account_summary_v1.md`, `prompts/judge_v1.md`, `prompts/CHANGELOG.md` |

---

## Dataset Policy

The assessment specifies that the solution must use only the official mock dataset from the starter repository:

```txt
data/tickets.json
data/accounts.json
knowledge-base/**/*.md
```

This project **does not fabricate replacement data**.

If the official files are missing or empty:

- `GET /dataset/status` reports what is present or missing.
- Ticket triage still works because it accepts a new incoming ticket directly.
- Knowledge-base matching is disabled when KB docs are absent to avoid hallucinated known-issue matches.
- Account brief generation returns a clear dataset/account precondition error instead of inventing account records.
- Evaluation reports still generate with `dataset_ready=false`.
- Account-summary eval cases that require official data are marked failed/skipped-style with score `0` and explanatory notes.

This behavior is intentional and aligned with the assessment rule that no external or fabricated data should be introduced.

---

## Architecture

```txt
External input
     │
     ▼
Streamlit UI / FastAPI API
     │
     ├── Ticket Triage Input
     │       │
     │       ▼
     │   app/triage_agent.py
     │       ├── app/pii.py                 ← local PII redaction
     │       ├── app/retrieval.py           ← TF-IDF KB retrieval
     │       ├── app/kb_loader.py           ← Markdown KB loader
     │       ├── app/llm_client.py          ← Groq/OpenAI-compatible optional LLM
     │       └── prompts/triage_v1.md       ← versioned prompt
     │
     ├── Account Brief Input
     │       │
     │       ▼
     │   app/account_summarizer.py
     │       ├── app/data_loader.py         ← flexible JSON loader
     │       ├── app/pii.py                 ← local PII redaction
     │       ├── app/llm_client.py          ← optional LLM
     │       └── prompts/account_summary_v1.md
     │
     └── Evaluation Harness
             │
             ▼
         evals/run_evals.py
             ├── evals/scoring.py
             ├── evals/report.py
             └── evals/test_cases/
```

---

## Project Structure

```txt
.
├── app/
│   ├── main.py
│   ├── config.py
│   ├── schemas.py
│   ├── data_loader.py
│   ├── kb_loader.py
│   ├── retrieval.py
│   ├── pii.py
│   ├── llm_client.py
│   ├── prompt_loader.py
│   ├── triage_agent.py
│   ├── account_summarizer.py
│   └── streaming.py
├── data/
│   ├── tickets.json
│   └── accounts.json
├── knowledge-base/
├── prompts/
│   ├── triage_v1.md
│   ├── account_summary_v1.md
│   ├── judge_v1.md
│   └── CHANGELOG.md
├── evals/
│   ├── run_evals.py
│   ├── scoring.py
│   ├── report.py
│   └── test_cases/
├── ui/
│   └── streamlit_app.py
├── tests/
├── scripts/
├── .github/workflows/
├── .env.example
├── requirements.txt
├── run.py
├── README.md
├── DESIGN_NOTE.md
├── eval_report.json
└── eval_report.md
```

---

## Setup

### 1. Clone the repository

```bash
git clone <YOUR_REPO_URL>
cd <YOUR_REPO_NAME>
```

### 2. Create virtual environment

```bash
python -m venv .venv
```

Activate it:

```bash
# macOS / Linux
source .venv/bin/activate
```

```bash
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the example file:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Fill `.env` locally.

For Groq via OpenAI-compatible API:

```env
OPENAI_API_KEY=your_groq_api_key_here
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_MODEL=llama-3.3-70b-versatile
LLM_TEMPERATURE=0
LLM_SEED=42
```

Never commit `.env`.

Only `.env.example` should be committed, and it must contain placeholders only.

---

## Environment Variables

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | Groq/OpenAI-compatible API key |
| `OPENAI_BASE_URL` | Optional OpenAI-compatible base URL, for Groq use `https://api.groq.com/openai/v1` |
| `OPENAI_MODEL` | Model name, for example `llama-3.3-70b-versatile` |
| `LLM_TEMPERATURE` | Set to `0` for deterministic behavior |
| `LLM_SEED` | Seed value where supported |
| `DATA_DIR` | Dataset directory |
| `TICKETS_FILE` | Path to official tickets JSON |
| `ACCOUNTS_FILE` | Path to official accounts JSON |
| `KB_DIR` | Path to official Markdown knowledge base |
| `PROMPT_DIR` | Prompt directory |
| `TRIAGE_PROMPT_VERSION` | Triage prompt version |
| `ACCOUNT_PROMPT_VERSION` | Account summary prompt version |
| `JUDGE_PROMPT_VERSION` | Eval judge prompt version |
| `TOP_K_KB_DOCS` | Number of retrieved KB docs |
| `EVAL_REPORT_JSON` | JSON eval report path |
| `EVAL_REPORT_MD` | Markdown eval report path |

---

## Running the FastAPI Server

```bash
python run.py
```

Then open:

```txt
http://localhost:8000/docs
```

Health check:

```bash
curl http://localhost:8000/health
```

Dataset status:

```bash
curl http://localhost:8000/dataset/status
```

---

## Running the Streamlit UI

```bash
streamlit run ui/streamlit_app.py
```

Local URL:

```txt
http://localhost:8501
```

Deployed URL:

```txt
https://zycustask-gtwa2frvp5zebf3djbn3m6.streamlit.app/
```

---

## Task 1 — Ticket Triage

### API Endpoint

```txt
POST /triage
```

### Sample Request

```bash
curl -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Production outage: all users unable to access the platform after SSO change",
    "body": "All users across the customer account are unable to log in after an SSO/SAML configuration update this morning. This is blocking production access for the entire team, including admins and support users. The customer has no workaround and is requesting immediate escalation because business operations are stopped."
  }'
```

### Expected Response Fields

```json
{
  "product_area": "...",
  "issue_category": "...",
  "urgency_tier": "P1",
  "reasoning": "...",
  "known_issue_match": {
    "matched": false,
    "doc_title": null,
    "doc_path": null,
    "match_reason": "...",
    "confidence": 0.0
  },
  "recommended_team": "...",
  "draft_first_response": "...",
  "retrieved_docs": [],
  "prompt_version": "triage_v1"
}
```

If the knowledge base is missing, the system should not hallucinate a match. It should return `known_issue_match.matched=false`.

---

## Task 2 — TAM Account Health Summariser

### API Endpoint

```txt
POST /accounts/{account_id}/brief
```

### Sample Request

```bash
curl -X POST http://localhost:8000/accounts/PLACEHOLDER_ACCOUNT_ID_REPLACE_WITH_OFFICIAL/brief
```

Replace the placeholder with an actual account ID from the official starter dataset.

### Output Sections

The account brief contains:

```txt
1. Executive summary, 3–5 sentences
2. Open risks and flagged issues
3. Recommended talking points
```

Risk flags must include a direct quote from the relevant ticket.

If official account/ticket data is unavailable, the system returns a clear precondition error instead of inventing account records.

---

## Task 3 — Evaluation Harness

Run:

```bash
python -m evals.run_evals
```

Expected outputs:

```txt
eval_report.json
eval_report.md
```

The eval harness includes:

```txt
5+ ticket triage test cases
5+ account-summary test cases
At least one adversarial test per task
Pass/fail result per test case
Quality score from 0–1 per test case
Summary report as JSON and Markdown
```

If official dataset is missing:

```txt
dataset_ready=false
```

Account-summary cases that require the official dataset are reported with score `0` and explanatory notes. They are not fabricated.

---

## Task 4 — Design Note Summary

Full design note: [`DESIGN_NOTE.md`](DESIGN_NOTE.md)

### 1. Failure Modes

The top production failure modes are:

1. **Incorrect KB retrieval** — the triage system may retrieve the wrong documentation if lexical overlap is weak or KB content is sparse. This is detected through low retrieval scores and eval failures, and mitigated with top-k retrieval, explicit no-match behavior, and known-issue doc path validation.
2. **Invalid or hallucinated LLM output** — an LLM may return malformed JSON, invalid urgency, or invented KB references. This is mitigated using strict JSON parsing, Pydantic validation, post-processing, deterministic fallback, and doc-path verification.
3. **Missed churn or escalation signals** — the account brief system may fail to identify renewal, cancellation, escalation, or SLA risk. This is mitigated with local keyword-based risk candidate detection and mandatory direct quote verification.

### 2. Latency vs Quality

The system uses lightweight TF-IDF retrieval instead of a vector database to keep setup simple and response time low for the assessment environment. This trades off some semantic retrieval quality for deterministic, dependency-light execution. If latency became the hard constraint, the next step would be caching loaded KB indexes, caching dataset parsing, and precomputing account ticket windows.

### 3. Data Sensitivity

Ticket and account text may contain PII. The system includes local redaction for emails, phone numbers, IP addresses, long identifiers, and secret-like values before LLM prompt construction. Real API keys are stored only in `.env` locally or Streamlit secrets in deployment. `.env.example` contains placeholders only.

### 4. Scaling to 10× Ticket Volume

At 10× volume, the first bottleneck would be linear JSON scans over accounts and tickets, followed by repeated TF-IDF index construction if not cached. In production, JSON files should be replaced with indexed storage, retrieval indexes should be persisted or cached, and eval runs should be batched.

---

## Bonus Features

| Bonus | Status | Implementation |
|---|---|---|
| Thin UI demo | Implemented | Streamlit app at `ui/streamlit_app.py` |
| Streaming output | Implemented if enabled | `app/streaming.py`, `/accounts/{account_id}/brief/stream` |
| CI eval run | Implemented if enabled | `.github/workflows/evals.yml` |
| Prompt versioning | Implemented | `prompts/*.md`, `prompts/CHANGELOG.md` |

---

## REST API Quick Reference

### Health

```bash
curl http://localhost:8000/health
```

### Dataset Status

```bash
curl http://localhost:8000/dataset/status
```

### Ticket Triage

```bash
curl -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -d '{"subject": "SSO broken", "body": "SAML login fails for all users since 09:00"}'
```

### Account Brief

```bash
curl -X POST http://localhost:8000/accounts/<ACCOUNT_ID>/brief
```

### Run Evals

```bash
curl -X POST http://localhost:8000/evals/run
```

---

## Streamlit Cloud Secrets

The deployed Streamlit app does not use `.env`.

Add secrets in Streamlit Cloud using TOML format:

```toml
OPENAI_API_KEY = "your_api_key_here"
OPENAI_BASE_URL = "https://api.groq.com/openai/v1"
OPENAI_MODEL = "llama-3.3-70b-versatile"
LLM_TEMPERATURE = "0"
LLM_SEED = "42"

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

Do not commit `.streamlit/secrets.toml`.

---

## Secret Safety

Before committing:

```bash
git check-ignore -v .env
git ls-files .env
```

Expected:

```txt
.env is ignored
git ls-files .env prints nothing
```

Run the secret scanner if available:

```bash
python scripts/check_secrets.py
```

Never commit:

```txt
.env
real API keys
Groq/OpenAI keys
Streamlit secrets
```

---

## Running Tests

```bash
pytest
```

Compile check:

```bash
python -m compileall app evals tests ui scripts
```

Run eval harness:

```bash
python -m evals.run_evals
```

---

## Known Limitations

1. **Official dataset availability**  
   If `data/accounts.json`, `data/tickets.json`, or `knowledge-base/` are absent or empty, account brief generation and account eval cases report clear precondition failures. This is by design.

2. **Knowledge-base retrieval**  
   Retrieval uses TF-IDF lexical similarity. It is deterministic and lightweight but less semantically powerful than embeddings.

3. **LLM dependency**  
   Groq/OpenAI-compatible LLM usage is optional. If unavailable, Task 1 triage should fall back to deterministic local logic.

4. **Linear JSON scans**  
   File-based loading is sufficient for the assessment dataset size but should be replaced by indexed storage for production scale.

5. **Streamlit deployment dataset state**  
   If the official dataset is not committed to the deployed repository, the live Streamlit app will show `dataset_ready=false` and will not fabricate account outputs.

---

## Submission Checklist

```txt
[ ] GitHub repo is public/shared
[ ] README.md complete
[ ] DESIGN_NOTE.md complete
[ ] .env.example committed with placeholders only
[ ] .env not committed
[ ] Streamlit app link added
[ ] Loom walkthrough link added
[ ] Task 1 triage demo works
[ ] Task 2 account brief works when official dataset is available
[ ] Eval harness generates eval_report.json or eval_report.md
[ ] No external/fake data used
[ ] No credentials committed
```

---

## Final Notes

This project prioritizes correctness, safety, and transparent handling of missing official data. Ticket triage can run from direct user input, while account health summarisation depends on the official assessment dataset. The system reports missing data honestly instead of fabricating outputs.
