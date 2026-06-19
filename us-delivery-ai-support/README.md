# US Delivery AI Support Tools

## Overview

This project implements AI-assisted tooling for internal Technical Support and
TAM teams. It includes intelligent ticket triage, TAM account health briefs, an
evaluation harness, and production-focused safeguards (PII redaction, missing-data
safety, deterministic fallbacks, prompt versioning, and a secret scanner).

It is built for the US Delivery Internship technical task round and is designed to
run end-to-end **even when the official mock dataset is absent**, failing
gracefully for data-dependent actions rather than fabricating data.

## Assessment Mapping

| Assessment item | Implementation |
|---|---|
| Task 1: ticket triage | `app/triage_agent.py`, `POST /triage` |
| Task 2: account health summariser | `app/account_summarizer.py`, `POST /accounts/{account_id}/brief` |
| Task 3: eval harness | `evals/run_evals.py`, `eval_report.json` / `eval_report.md` |
| Task 4: design note | `DESIGN_NOTE.md` |
| Bonus UI | `ui/streamlit_app.py` |
| Bonus streaming | `POST /accounts/{account_id}/brief/stream` |
| Bonus CI | `.github/workflows/evals.yml` |
| Bonus prompt versioning | `prompts/*.md`, `prompts/CHANGELOG.md` |

## Architecture

```
app/
  config.py            Settings (pydantic-settings, .env)
  schemas.py           Pydantic contracts for all I/O and AI outputs
  data_loader.py       Official dataset loading + readiness/missing-data safety
  kb_loader.py         Markdown knowledge-base loader
  retrieval.py         TF-IDF knowledge-base retrieval
  pii.py               Local PII redaction
  llm_client.py        OpenAI-compatible client (deterministic defaults)
  prompt_loader.py     Versioned prompt loading + rendering
  triage_agent.py      Task 1 — ticket triage
  account_summarizer.py Task 2 — TAM account brief (quote-verified risks)
  streaming.py         Bonus — deterministic NDJSON streaming for Task 2
  main.py              FastAPI app and routes
evals/
  scoring.py           Deterministic rule-based scoring
  run_evals.py         Eval runner + report generation
  report.py            JSON + Markdown report writers
  test_cases/          Triage and account-summary eval cases
ui/streamlit_app.py    Bonus thin UI
scripts/
  check_secrets.py     Local secret scanner
  final_validate.py    Submission-readiness validation
prompts/               Versioned prompts + CHANGELOG
```

## Dataset Requirement

The assessment requires using **only** the mock dataset from the starter repo:

- `data/tickets.json`
- `data/accounts.json`
- `knowledge-base/**/*.md`

This repository **does not fabricate replacement data**. If official files are
missing or empty, data-dependent features return clear dataset readiness errors,
and the eval harness still runs and reports `dataset_ready=false`.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# Windows:
.venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env
```

- Put your real key **only** in `.env`.
- **Never commit `.env`.** It is gitignored.
- For Groq, use the OpenAI-compatible env names (`OPENAI_API_KEY`,
  `OPENAI_BASE_URL=https://api.groq.com/openai/v1`, `OPENAI_MODEL=...`).

The app and tests run without an API key — LLM-dependent paths use a
deterministic local fallback.

## Environment Variables

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | API key (OpenAI or OpenAI-compatible provider). Local only. |
| `OPENAI_BASE_URL` | Provider base URL (e.g. Groq). Empty for OpenAI default. |
| `OPENAI_MODEL` | Model name. |
| `LLM_TEMPERATURE` | Sampling temperature (default 0 for determinism). |
| `LLM_SEED` | Sampling seed (default 42). |
| `DATA_DIR` | Dataset directory. |
| `TICKETS_FILE` | Path to official tickets JSON. |
| `ACCOUNTS_FILE` | Path to official accounts JSON. |
| `KB_DIR` | Knowledge-base directory. |
| `PROMPT_DIR` | Prompt directory. |
| `TOP_K_KB_DOCS` | Number of KB docs retrieved for triage. |
| `EVAL_REPORT_JSON` | Eval JSON report path. |
| `EVAL_REPORT_MD` | Eval Markdown report path. |

Do not put real keys in `.env.example` — it contains placeholders only.

## Running the API

```bash
python run.py
```

```bash
curl http://localhost:8000/health
curl http://localhost:8000/dataset/status
```

Interactive docs: `http://localhost:8000/docs`.

## Running the Streamlit UI

```bash
streamlit run ui/streamlit_app.py
```

The UI provides Dataset Status, Ticket Triage, TAM Account Brief (with an
optional streaming display), Eval Report, and About sections. It never displays
secrets and never fabricates data.

## Task 1: Ticket Triage Sample Run

```bash
curl -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "SSO login issue",
    "body": "Users are unable to log in after a SAML configuration update."
  }'
```

The response contains: `product_area`, `issue_category`, `urgency_tier`
(P1–P4), `reasoning`, `known_issue_match`, `recommended_team`,
`draft_first_response`, `retrieved_docs`, and `prompt_version`. Exact values
depend on the configured model and the available knowledge base.

## Task 2: TAM Account Brief Sample Run

```bash
curl -X POST http://localhost:8000/accounts/PLACEHOLDER_ACCOUNT_ID_REPLACE_WITH_OFFICIAL/brief
```

Replace the placeholder with an actual account ID from the official
`accounts.json`. Every flagged risk includes a `evidence_quote` that is verified
against real ticket text; unverifiable risks are dropped rather than invented.
If the dataset is missing, the endpoint returns a dataset-readiness error.

Streaming (bonus, NDJSON section-by-section):

```bash
curl -N -X POST http://localhost:8000/accounts/PLACEHOLDER_ACCOUNT_ID_REPLACE_WITH_OFFICIAL/brief/stream
```

If the dataset is missing, the stream emits a controlled error chunk instead of
crashing.

## Task 3: Evaluation Harness

```bash
python -m evals.run_evals
```

Outputs:

- `eval_report.json`
- `eval_report.md`

If the dataset is missing, the report is still generated with
`dataset_ready=false`; account cases that require official data fail gracefully
with explanatory notes, and triage cases run via the deterministic fallback.

## Bonus Features

- **Thin UI** — `ui/streamlit_app.py`.
- **Streaming** — `POST /accounts/{account_id}/brief/stream` (deterministic NDJSON).
- **CI** — `.github/workflows/evals.yml` runs secret scan, tests, compile, and evals.
- **Prompt versioning** — `prompts/*.md` with identifiers and `prompts/CHANGELOG.md`.

## Design Note

See `DESIGN_NOTE.md` for failure modes, latency vs quality, data sensitivity,
and scaling to 10x ticket volume.

## Repository Safety / Secrets

```bash
python scripts/check_secrets.py
git check-ignore -v .env
git ls-files .env
```

Expected: `.env` is ignored, `git ls-files .env` prints nothing, and no real
secrets are detected. Never commit `.env`. If a key was ever exposed, rotate it
in the provider console — this cannot be undone by removing it from a file.

## Known Dataset Status

This repository ships **without** the official mock dataset. `data/*.json` may
be empty and `knowledge-base/` may have no docs. This is intentional: no
fabricated official data is included. Run `GET /dataset/status` or
`python scripts/final_validate.py` to see current readiness, and see
`LATE_DATASET_INSTRUCTIONS.md` for how to add the official files.

## Submission Notes

See `SUBMISSION_CHECKLIST.md` and `LOOM_SCRIPT.md`.

## Final Validation

Run:

```bash
python scripts/final_validate.py
```

For strict validation after official data is available:

```bash
python scripts/final_validate.py --strict
```

See:
- `FINAL_VALIDATION.md`
- `LATE_DATASET_INSTRUCTIONS.md`
- `SUBMISSION_CHECKLIST.md`
- `LOOM_SCRIPT.md`
