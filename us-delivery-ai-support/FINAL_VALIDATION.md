# Final Validation Report

## Summary

| Status | Count |
|---|---:|
| PASS | 23 |
| WARN | 3 |
| FAIL | 0 |

## Checks

| Status | Check | Details |
|---|---|---|
| PASS | Required file: README.md | README.md |
| PASS | Required file: DESIGN_NOTE.md | DESIGN_NOTE.md |
| PASS | Required file: requirements.txt | requirements.txt |
| PASS | Required file: .env.example | .env.example |
| PASS | Required file: run.py | run.py |
| PASS | Required file: app/main.py | app/main.py |
| PASS | Required file: app/triage_agent.py | app/triage_agent.py |
| PASS | Required file: app/account_summarizer.py | app/account_summarizer.py |
| PASS | Required file: evals/run_evals.py | evals/run_evals.py |
| PASS | Required file: evals/scoring.py | evals/scoring.py |
| PASS | Required file: prompts/triage_v1.md | prompts/triage_v1.md |
| PASS | Required file: prompts/account_summary_v1.md | prompts/account_summary_v1.md |
| PASS | Required file: prompts/CHANGELOG.md | prompts/CHANGELOG.md |
| PASS | Bonus file: ui/streamlit_app.py | ui/streamlit_app.py |
| PASS | Bonus file: .github/workflows/evals.yml | .github/workflows/evals.yml |
| PASS | Bonus file: scripts/check_secrets.py | scripts/check_secrets.py |
| PASS | Bonus file: app/streaming.py | app/streaming.py |
| WARN | Dataset readiness | Official dataset is incomplete. Missing or empty: knowledge-base/**/*.md |
| PASS | Secret scan | no likely secrets detected |
| WARN | .env tracking | Git unavailable; could not verify |
| WARN | .env ignored | not reported as ignored |
| PASS | Eval report | report file present |
| PASS | README content | exists and mentions setup |
| PASS | DESIGN_NOTE content | covers all required prompts |
| PASS | Doc: SUBMISSION_CHECKLIST.md | SUBMISSION_CHECKLIST.md |
| PASS | Doc: LOOM_SCRIPT.md | LOOM_SCRIPT.md |
