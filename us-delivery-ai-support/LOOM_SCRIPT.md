# Loom Walkthrough Script (3–6 minutes)

Record a 3–6 minute walkthrough. Two paths are provided depending on whether the
official dataset is present. Pick the matching path at the dataset-status step.

## Timed Outline

```
0:00–0:30  Overview
0:30–1:15  Architecture and files
1:15–2:15  Task 1 live demo
2:15–3:15  Task 2 live demo
3:15–4:15  Eval harness and report
4:15–5:00  Production considerations
5:00–5:30  Bonus features and closing
```

## Exact Commands

```bash
python run.py
# Open http://localhost:8000/docs
# POST /triage
# POST /accounts/{account_id}/brief
python -m evals.run_evals
streamlit run ui/streamlit_app.py
```

## 0:00–0:30 — Overview

"This is the US Delivery AI Support Tools project. It implements ticket triage,
a TAM account health summariser, an evaluation harness, a design note, and bonus
items: a Streamlit UI, streaming, and CI. It is built to run safely even when the
official dataset is missing."

## 0:30–1:15 — Architecture and files

Show the repo tree and `README.md` Assessment Mapping table. Point out `app/`
(triage agent, account summariser, schemas, retrieval, PII redaction, LLM
client), `evals/`, `ui/`, `scripts/`, and `prompts/` with the changelog.

## 1:15–2:15 — Task 1 live demo

Start the API (`python run.py`), open `/docs`, and run `POST /triage` with an SSO
login example. Walk through the structured fields: product area, urgency tier,
reasoning, known-issue match (note it only cites retrieved docs), recommended
team, and draft first response.

## 2:15–3:15 — Task 2 live demo

Run `POST /accounts/{account_id}/brief`.

- **If official dataset is available:** use a real official account ID. Show the
  executive summary, risks with verified `evidence_quote`s and ticket IDs, and
  talking points. Optionally show streaming via
  `POST /accounts/{account_id}/brief/stream`.

## 3:15–4:15 — Eval harness and report

Run `python -m evals.run_evals`. Open `eval_report.md`. Explain rule-based
scoring, the 0.70 pass threshold, adversarial cases, and the known-issue and
quote-verification safety checks.

## 4:15–5:00 — Production considerations

Summarise the design note: failure modes (KB retrieval, hallucinated output,
missed churn signal), deterministic defaults (temperature 0, seed), PII
redaction before any LLM call, and scaling to 10x volume (stateless API, bounded
90-day window, eval/CI regression gate).

## 5:00–5:30 — Bonus features and closing

Show the Streamlit UI (`streamlit run ui/streamlit_app.py`), mention CI
(`.github/workflows/evals.yml`) running secret scan + tests + evals on every
commit, and prompt versioning. Close on repository safety: `.env` is gitignored,
`.env.example` has placeholders only, and `scripts/check_secrets.py` enforces it.

---

## Dataset-Missing Path

If the official dataset is **not** present, use this path at the relevant steps
and state clearly on camera:

> "I am showing dataset readiness and graceful failure because the official
> dataset is not present. I did not fabricate replacement data."

- **Dataset status:** Show `GET /dataset/status` returning `ready: false`.
- **Task 1:** Run `POST /triage`; show the structural triage / deterministic
  fallback still produces a valid, schema-checked response.
- **Task 2:** Run `POST /accounts/{id}/brief` and show the system **refusing to
  fabricate** an account — it returns a clear dataset-readiness error.
- **Eval harness:** Run `python -m evals.run_evals`; open the report and show
  `dataset_ready=false`, with account cases failing gracefully and notes.
- **Closing:** List the exact files needed from the starter repo
  (`data/tickets.json`, `data/accounts.json`, `knowledge-base/**/*.md`) and
  point to `LATE_DATASET_INSTRUCTIONS.md`.
