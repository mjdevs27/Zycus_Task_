# Claude Code Prompt — Fix Task 3 Evaluation Runner Error Only

## Context

You are Claude Code working inside my **US Delivery AI Support Tools** project.

The project is for the **US Delivery Internship Technical Task Round**.

The assessment requires:

```txt
Task 3 — Evaluation harness
- At least 5 test cases per task.
- Expected outputs or acceptance criteria.
- Scoring function with pass/fail.
- Quality score from 0–1 per test case.
- Summary report as JSON or Markdown table.
- At least one adversarial test case per task.
```

Current issue:

In the Streamlit UI under:

```txt
Task 3 — Evaluation Report
```

when I click:

```txt
Run evals
```

the UI shows:

```txt
An unexpected error occurred while running evaluations.
```

Also, it says:

```txt
No eval report found yet. Click Run evals to generate eval_report.json and eval_report.md.
```

So the eval runner is crashing before generating:

```txt
eval_report.json
eval_report.md
```

Your job is to fix only the eval error issue.

---

## Strict Rules

Do not:

```txt
Create fake official tickets.
Create fake official accounts.
Create fake official knowledge-base docs.
Use external datasets.
Scrape external data.
Invent account summaries.
Invent direct ticket quotes.
Commit .env.
Print or expose API keys.
Make evals pass by fabricating data.
```

The official dataset may be missing. That must be handled honestly.

If official data is missing:

```txt
dataset_ready=false
```

must appear in the eval report.

Task 1 triage eval cases can still run because they provide direct ticket inputs.

Task 2 account-summary eval cases that require official dataset must not crash. They should be marked as failed/skipped-style results with score 0 and a clear note.

---

# Part 1 — Show the Real Error in Streamlit

Open:

```txt
ui/streamlit_app.py
```

Find the code for:

```txt
Task 3 — Evaluation Report
Run evals
```

If it currently has:

```python
except Exception:
    st.error("An unexpected error occurred while running evaluations.")
```

replace it with:

```python
except Exception as e:
    st.error("An unexpected error occurred while running evaluations.")
    with st.expander("Debug details"):
        st.exception(e)
```

This is required while debugging so the actual exception is visible.

For final submission, keep the traceback inside the expander or show it only in development mode.

---

# Part 2 — Inspect These Files

Inspect these files before editing:

```txt
evals/run_evals.py
evals/report.py
evals/scoring.py
evals/test_cases/triage_tests.json
evals/test_cases/account_summary_tests.json
app/schemas.py
app/data_loader.py
app/triage_agent.py
app/account_summarizer.py
ui/streamlit_app.py
```

Do not rewrite unrelated modules.

---

# Part 3 — Required Behavior for evals/run_evals.py

Open:

```txt
evals/run_evals.py
```

The command:

```bash
python -m evals.run_evals
```

must:

```txt
Load triage test cases.
Load account-summary test cases.
Check dataset status.
Run triage cases.
Handle account-summary cases requiring official dataset gracefully.
Generate eval_report.json.
Generate eval_report.md.
Return or print a summary.
Never crash only because official data is missing.
Never create fake data.
```

Expected logic:

```txt
1. Load evals/test_cases/triage_tests.json.
2. Load evals/test_cases/account_summary_tests.json.
3. Call check_dataset_status().
4. Set dataset_ready = status.ready.
5. Run triage cases through TicketTriageAgent.
6. For account cases:
   - if requires_official_dataset=true and dataset_ready=false:
     do not call AccountHealthSummarizer
     return failed EvalCaseResult
     score=0
     notes explain official dataset is not ready
   - otherwise run normally
7. Build EvalReport.
8. Write eval_report.json.
9. Write eval_report.md.
10. Return EvalReport.
```

Required note for dataset-dependent account cases when official data is missing:

```txt
Official dataset is not ready, so this account-summary case could not be executed without inventing account data.
```

Do not mark these cases as passed.

Do not generate fake account summaries.

---

# Part 4 — Fix run_account_case

In:

```txt
evals/run_evals.py
```

Implement or fix:

```python
def run_account_case(case: dict, summarizer: AccountHealthSummarizer, dataset_ready: bool) -> EvalCaseResult:
```

Required behavior:

```txt
If case["requires_official_dataset"] is true and dataset_ready is false:
- return EvalCaseResult
- passed=false
- score=0
- notes include official dataset not ready message
- adversarial copied from case
- id/name/task copied from case
```

Do not call AccountHealthSummarizer in this case.

If the case does not require official dataset:
- run normally
- catch exceptions
- return failed EvalCaseResult with notes
- do not crash the whole eval run

---

# Part 5 — Fix run_triage_case

In:

```txt
evals/run_evals.py
```

Implement or fix:

```python
def run_triage_case(case: dict, agent: TicketTriageAgent) -> EvalCaseResult:
```

Required behavior:

```txt
Triage eval cases should run even when official dataset is missing.
Build TicketTriageRequest from case["input"].
Call TicketTriageAgent.triage().
Score output with score_case().
If triage fails, catch the exception and return failed EvalCaseResult with clear notes.
Do not stop the whole eval run.
```

Task 1 should not require official dataset because test cases provide direct ticket text or subject/body.

---

# Part 6 — Fix EvalCaseResult / EvalReport Schema Mismatch

Open:

```txt
app/schemas.py
```

Check or create these schemas.

`EvalCaseResult` should support:

```txt
id: str
name: str
task: str
passed: bool
score: float
notes: list[str]
adversarial: bool
```

`EvalReport` should support:

```txt
generated_at: str
total_cases: int
passed_cases: int
failed_cases: int
average_score: float
results: list[EvalCaseResult]
dataset_ready: bool
```

If your schema uses different names, align either:
- the schemas with the eval runner, or
- the eval runner with the schemas

Do not leave mismatched field names.

---

# Part 7 — Fix evals/report.py

Open:

```txt
evals/report.py
```

It must write both:

```txt
eval_report.json
eval_report.md
```

even when dataset is missing.

Implement or fix:

```python
def model_to_dict(obj) -> dict:
```

Support:

```txt
Pydantic v2: model_dump()
Pydantic v1: dict()
plain dict
```

Implement or fix:

```python
def write_json_report(report: EvalReport, path: str | Path) -> None:
```

Requirements:

```txt
Create parent directories if needed.
Write UTF-8 JSON.
Indent 2.
Serialize Pydantic models correctly.
```

Implement or fix:

```python
def write_markdown_report(report: EvalReport, path: str | Path) -> None:
```

Markdown must include:

```txt
# Evaluation Report
Generated at
Dataset ready
Summary table
Results table
Notes
```

If dataset missing, Markdown must clearly include:

```txt
Dataset ready: false
```

Escape Markdown table pipes:

```python
str(value).replace("|", "\|")
```

---

# Part 8 — Fix evals/scoring.py Robustness

Open:

```txt
evals/scoring.py
```

Required behavior:

```txt
score_case() should not crash the full eval runner.
If output is invalid, return failed EvalCaseResult or scoring result with notes.
Scores must be clamped between 0 and 1.
Missing fields should create notes.
Invalid urgency should create notes.
Missing evidence quote should create notes.
```

Do not throw raw exceptions for ordinary bad model outputs.

If an internal unexpected error happens during scoring:
- catch it inside `score_case`
- return a failed result with the error message in notes

---

# Part 9 — Fix Streamlit Eval Section

Open:

```txt
ui/streamlit_app.py
```

The eval section should:

```txt
Run evals on button click.
Display summary after successful run.
Load eval_report.json if it exists.
Display table of results.
Show dataset_ready status.
Show friendly message if no report exists.
Show debug expander if eval run fails.
```

Expected behavior:

When user clicks:

```txt
Run evals
```

it should call:

```python
run_all_evals()
```

Then display:

```txt
total_cases
passed_cases
failed_cases
average_score
dataset_ready
```

If report exists, display results.

If report does not exist:

```txt
No eval report found yet. Click Run evals to generate eval_report.json and eval_report.md.
```

If run fails unexpectedly, show:

```python
with st.expander("Debug details"):
    st.exception(e)
```

---

# Part 10 — Required Commands After Fix

Run:

```bash
python -m evals.run_evals
```

Expected:

```txt
No crash.
eval_report.json generated.
eval_report.md generated.
If official dataset is missing, dataset_ready=false.
Account-summary cases requiring official dataset have score 0 and clear notes.
```

Then run:

```bash
python -m compileall app evals ui tests
```

Then run:

```bash
pytest tests/test_eval_runner.py tests/test_eval_scoring.py tests/test_eval_cases.py
```

If these tests do not exist, create or update them minimally to cover the fixed behavior.

Then run Streamlit:

```bash
streamlit run ui/streamlit_app.py
```

Click:

```txt
Task 3 — Evaluation Report
Run evals
```

Expected:

```txt
No unexpected error.
Report summary appears.
Report table appears.
Dataset readiness is displayed.
```

---

# Part 11 — Tests to Add or Fix

Add or fix tests for:

```txt
run_all_evals generates report when dataset_ready=false
run_account_case returns failed result without calling summarizer when dataset missing
write_json_report creates valid JSON
write_markdown_report creates Markdown table
score_case returns score between 0 and 1
```

Do not require official dataset for these tests.

Do not require API key for these tests.

---

# Final Acceptance Criteria

The eval fix is complete only when:

```txt
[ ] python -m evals.run_evals does not crash.
[ ] eval_report.json is generated.
[ ] eval_report.md is generated.
[ ] Streamlit Run evals button does not crash.
[ ] Dataset missing state is shown honestly.
[ ] dataset_ready=false appears when official dataset is missing.
[ ] Account-summary eval cases do not invent data.
[ ] Triage eval cases still run or fail gracefully without stopping the runner.
[ ] Report includes pass/fail and quality score 0–1 per case.
[ ] No fake official data was created.
[ ] No real secrets were printed or committed.
```

Implement only the eval error fix. Do not modify unrelated features unless required for eval execution.
