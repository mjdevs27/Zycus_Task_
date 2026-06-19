# Claude Code Prompt — Fix Run Evals Failure and Show 10-Case Evaluation Table

## Context

You are Claude Code working inside my **US Delivery AI Support Tools** project.

The project is for the **US Delivery Internship Technical Task Round**.

The assessment requires **Task 3 — Evaluation Harness**:

```txt
- Test both Task 1 and Task 2 outputs systematically.
- Define at least 5 test cases per task.
- Implement scoring with pass/fail and quality score 0–1 per test case.
- Produce a summary report as JSON or Markdown table.
- Include at least one adversarial test case per task.
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

it fails and shows:

```txt
An unexpected error occurred while running evaluations.
```

I want this fixed so that clicking **Run evals** shows a proper evaluation report table.

---

## Exact Desired Output

When I click **Run evals**, the UI should show:

```txt
Total cases: 10
Passed cases: something realistic
Failed cases: something realistic
Average score: 0.xx
Dataset ready: true/false
```

Then a table with **10 rows**:

```txt
5 Task 1 triage eval cases
5 Task 2 account-summary eval cases
```

If official dataset is missing:

```txt
dataset_ready=false
```

Expected honest behavior when dataset is missing:

```txt
- 5 triage cases should run because they use direct ticket input.
- 5 account-summary cases should not hallucinate account data.
- Account-summary cases requiring official data should be marked failed/skipped-style with score 0.
- The table should still have all 10 cases.
```

So if triage fallback works and all 5 triage cases pass, while 5 account cases fail due to missing official dataset, the report may show roughly:

```txt
Total cases: 10
Passed cases: 5
Failed cases: 5
Pass rate: 50%
Dataset ready: false
```

Do not hardcode 50%. Calculate it from results. But the missing-dataset case will likely naturally become 5/10 if all triage cases pass and all account cases are dataset-blocked.

---

## Non-Negotiable Rules

Do not:

```txt
Create fake official tickets.
Create fake official accounts.
Create fake official KB docs.
Use external datasets.
Scrape external data.
Invent account summaries.
Invent direct ticket quotes.
Make evals pass by fabricating data.
Hide missing dataset.
Commit .env.
Print or expose real API keys.
```

If official dataset is missing, the report must say that honestly.

---

# Part 1 — Show the Real Streamlit Error During Debugging

Open:

```txt
ui/streamlit_app.py
```

Find the code handling:

```txt
Task 3 — Evaluation Report
Run evals
```

If it has:

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

This is required during debugging.

For final submission, keep the traceback inside an expander or only show it when:

```python
settings.app_env == "development"
```

---

# Part 2 — Inspect These Files

Inspect these files:

```txt
ui/streamlit_app.py
evals/run_evals.py
evals/report.py
evals/scoring.py
evals/test_cases/triage_tests.json
evals/test_cases/account_summary_tests.json
app/schemas.py
app/data_loader.py
app/triage_agent.py
app/account_summarizer.py
```

Do not rewrite unrelated features.

---

# Part 3 — Ensure There Are Exactly 5+5 Eval Cases

Check:

```txt
evals/test_cases/triage_tests.json
evals/test_cases/account_summary_tests.json
```

Requirements:

```txt
triage_tests.json must have at least 5 cases.
account_summary_tests.json must have at least 5 cases.
At least one adversarial case per task.
```

For this fix, the UI should display the first 5 triage cases and first 5 account cases if more exist, or all cases if exactly 5+5 exist.

Do not delete extra cases unless they are broken. But the table must show at least 10 total cases.

Account-summary cases that require official data should include:

```json
"requires_official_dataset": true
```

Example:

```json
{
  "id": "account_001",
  "name": "Account brief contains required three sections",
  "task": "account_summary",
  "input": {
    "account_id": "PLACEHOLDER_ACCOUNT_ID_REPLACE_WITH_OFFICIAL"
  },
  "acceptance_criteria": {
    "required_fields": [
      "account_id",
      "executive_summary",
      "open_risks_and_flagged_issues",
      "recommended_talking_points"
    ],
    "executive_summary_sentence_range": [3, 5],
    "requires_direct_ticket_quote_for_each_risk": true,
    "minimum_talking_points": 1
  },
  "adversarial": false,
  "requires_official_dataset": true
}
```

Do not use fake account IDs that look real.

Use placeholder labels only.

---

# Part 4 — Fix evals/run_evals.py

Open:

```txt
evals/run_evals.py
```

The command:

```bash
python -m evals.run_evals
```

must not crash.

It must:

```txt
1. Load triage eval cases.
2. Load account-summary eval cases.
3. Check dataset readiness using check_dataset_status().
4. Run triage eval cases.
5. Handle account-summary eval cases gracefully if official dataset is missing.
6. Build EvalReport.
7. Write eval_report.json.
8. Write eval_report.md.
9. Return EvalReport.
```

Implement or fix:

```python
def run_all_evals(
    triage_cases_path="evals/test_cases/triage_tests.json",
    account_cases_path="evals/test_cases/account_summary_tests.json",
    output_json_path="eval_report.json",
    output_md_path="eval_report.md",
) -> EvalReport:
    ...
```

Expected behavior:

```txt
If dataset_ready=false:
- still run triage cases
- do not call AccountHealthSummarizer for account cases requiring official dataset
- return failed EvalCaseResult for those account cases
- score=0
- notes explain dataset is not ready
- still generate the final report
```

Required note:

```txt
Official dataset is not ready, so this account-summary case could not be executed without inventing account data.
```

Do not mark those account cases as passed.

Do not skip them completely. They must appear in the 10-row table.

---

# Part 5 — Fix run_account_case

In:

```txt
evals/run_evals.py
```

Implement or fix:

```python
def run_account_case(case: dict, summarizer: AccountHealthSummarizer, dataset_ready: bool) -> EvalCaseResult:
```

Required logic:

```python
if case.get("requires_official_dataset", False) and not dataset_ready:
    return EvalCaseResult(
        id=case["id"],
        name=case["name"],
        task=case.get("task", "account_summary"),
        passed=False,
        score=0.0,
        notes=[
            "Official dataset is not ready, so this account-summary case could not be executed without inventing account data."
        ],
        adversarial=bool(case.get("adversarial", False)),
    )
```

Then normal execution only if dataset is ready or the case does not require official dataset.

If summarizer raises an exception:
- catch it
- return failed EvalCaseResult
- add exception message to notes
- do not crash the entire eval run

---

# Part 6 — Fix run_triage_case

In:

```txt
evals/run_evals.py
```

Implement or fix:

```python
def run_triage_case(case: dict, agent: TicketTriageAgent) -> EvalCaseResult:
```

Required logic:

```txt
- Build TicketTriageRequest from case["input"].
- Call agent.triage(request).
- Score output using score_case().
- If triage fails, catch the exception.
- Return failed EvalCaseResult with notes.
- Do not stop entire eval run.
```

Task 1 evals should not require official dataset.

If LLM fails, triage fallback should still return valid output.

If triage fallback is not working, fix app/triage_agent.py.

---

# Part 7 — Fix EvalReport Schema Compatibility

Open:

```txt
app/schemas.py
```

Ensure `EvalCaseResult` supports:

```txt
id: str
name: str
task: str
passed: bool
score: float
notes: list[str]
adversarial: bool
```

Ensure `EvalReport` supports:

```txt
generated_at: str
total_cases: int
passed_cases: int
failed_cases: int
average_score: float
results: list[EvalCaseResult]
dataset_ready: bool
```

If your schema uses different field names, align the eval runner and Streamlit UI to the actual schema.

Do not leave schema mismatch.

---

# Part 8 — Build Report With Correct Counts

In:

```txt
evals/run_evals.py
```

Implement or fix:

```python
def build_eval_report(results: list[EvalCaseResult], dataset_ready: bool) -> EvalReport:
```

Required calculations:

```python
total_cases = len(results)
passed_cases = sum(1 for r in results if r.passed)
failed_cases = total_cases - passed_cases
average_score = round(sum(r.score for r in results) / total_cases, 3) if total_cases else 0
```

Then return `EvalReport`.

If there are 10 cases and 5 pass, the report should naturally show:

```txt
total_cases=10
passed_cases=5
failed_cases=5
average_score=...
dataset_ready=false
```

Do not hardcode passed count.

---

# Part 9 — Fix evals/report.py

Open:

```txt
evals/report.py
```

Implement or fix:

```python
def model_to_dict(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if isinstance(obj, dict):
        return obj
    raise TypeError(...)
```

Implement or fix:

```python
def write_json_report(report: EvalReport, path: str | Path) -> None:
```

Requirements:

```txt
Create parent dirs if needed.
Serialize Pydantic models.
Write UTF-8 JSON.
Indent 2.
```

Implement or fix:

```python
def write_markdown_report(report: EvalReport, path: str | Path) -> None:
```

Markdown must include:

```txt
# Evaluation Report
Dataset ready: false
Summary table
10-row results table
Notes column
```

Results table columns:

```txt
ID
Task
Name
Passed
Score
Adversarial
Notes
```

Escape Markdown pipe characters:

```python
str(value).replace("|", "\|")
```

---

# Part 10 — Fix Streamlit Eval UI Table

Open:

```txt
ui/streamlit_app.py
```

In the Eval Report section, after running evals, display summary metrics:

```python
st.metric("Total cases", report.total_cases)
st.metric("Passed", report.passed_cases)
st.metric("Failed", report.failed_cases)
st.metric("Average score", report.average_score)
st.write("Dataset ready:", report.dataset_ready)
```

Then display a table.

Convert results to dataframe-friendly rows:

```python
rows = []
for r in report.results:
    data = r.model_dump() if hasattr(r, "model_dump") else r.dict()
    rows.append({
        "ID": data.get("id"),
        "Task": data.get("task"),
        "Name": data.get("name"),
        "Passed": data.get("passed"),
        "Score": data.get("score"),
        "Adversarial": data.get("adversarial"),
        "Notes": "; ".join(data.get("notes", [])),
    })

st.dataframe(rows, use_container_width=True)
```

If report is a dict, support dict format too.

When loading existing `eval_report.json`, parse it and show the same summary/table.

---

# Part 11 — Expected Streamlit Output

After fix, clicking **Run evals** should show something like:

```txt
Total cases: 10
Passed: 5
Failed: 5
Average score: 0.50
Dataset ready: false
```

Then table:

```txt
triage_001     triage           ...     passed true/false     score ...
triage_002     triage           ...     passed true/false     score ...
triage_003     triage           ...     passed true/false     score ...
triage_004     triage           ...     passed true/false     score ...
triage_005     triage           ...     passed true/false     score ...
account_001    account_summary  ...     passed false          score 0
account_002    account_summary  ...     passed false          score 0
account_003    account_summary  ...     passed false          score 0
account_004    account_summary  ...     passed false          score 0
account_005    account_summary  ...     passed false          score 0
```

Do not hardcode table values. Generate from eval results.

---

# Part 12 — Tests to Add or Fix

Add or fix tests:

```txt
tests/test_eval_runner.py
tests/test_eval_scoring.py
tests/test_eval_cases.py
```

Minimum tests:

```txt
1. run_all_evals generates report when dataset_ready=false.
2. run_account_case returns failed result with score 0 when dataset missing.
3. run_account_case does not call summarizer when dataset missing and requires_official_dataset=true.
4. build_eval_report returns correct counts.
5. write_json_report writes valid JSON.
6. write_markdown_report writes Markdown with results table.
7. eval case files have at least 5 cases per task.
8. at least one adversarial case per task.
```

Tests must not require:
- official dataset
- real API key
- external services

---

# Part 13 — Commands to Run

Run:

```bash
python -m evals.run_evals
```

Expected:

```txt
No crash.
eval_report.json generated.
eval_report.md generated.
total_cases is 10 or more.
dataset_ready=false if official data missing.
```

Then:

```bash
python -m compileall app evals ui tests
pytest tests/test_eval_runner.py tests/test_eval_scoring.py tests/test_eval_cases.py
```

Then:

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
10-case table appears.
Summary metrics appear.
Dataset ready false appears if official dataset missing.
```

---

# Final Acceptance Criteria

The fix is complete only when:

```txt
[ ] Clicking Run evals does not fail.
[ ] Streamlit displays summary metrics.
[ ] Streamlit displays a table with 10 cases.
[ ] eval_report.json is generated.
[ ] eval_report.md is generated.
[ ] dataset_ready=false appears when official dataset is missing.
[ ] Account-summary cases are shown in the table with score 0 when dataset missing.
[ ] Triage cases still run or fail gracefully without stopping the report.
[ ] No fake official data is created.
[ ] No real secrets are printed or committed.
```

Implement this fix now.
