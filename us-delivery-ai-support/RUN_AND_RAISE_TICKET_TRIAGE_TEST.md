# Run the App and Raise/Test a Ticket Without Official Dataset

## Purpose

This MD is for Claude Code to verify that the project can run locally and that **Task 1 ticket triage** works independently of the missing official dataset.

The assessment requires Task 1 to accept a raw ticket as text or JSON with `subject + body`, classify it, assign urgency P1–P4, suggest a responder team, identify any known issue from the knowledge base when available, and return a draft first response. FastAPI is acceptable for exposing the endpoint.

Important context:

```txt
The official dataset may still be missing or empty.
Ticket triage must still be testable because a new incoming ticket can be provided directly by the user.
If the knowledge-base docs are missing, the app must not hallucinate a KB match.
The endpoint should still return a valid triage response using LLM or local fallback.
```

This MD focuses only on:

```txt
1. Installing dependencies.
2. Verifying .env and secret safety.
3. Starting the FastAPI app.
4. Opening the local API docs link.
5. Raising a ticket through /triage.
6. Testing the endpoint using curl, PowerShell, and Swagger UI.
7. Confirming behavior when dataset/KB is missing.
8. Fixing common errors.
```

---

## Non-Negotiable Rules

Do not:

```txt
Create fake official tickets.
Create fake official accounts.
Create fake official KB docs.
Use external datasets.
Commit .env.
Expose real API keys in README, logs, screenshots, or terminal output.
Let the LLM hallucinate a known issue doc when KB docs are unavailable.
```

The `.env` file may contain a real local key, but it must remain Git-ignored.

---

## Step 1 — Confirm You Are in the Project Root

Run:

```bash
pwd
ls
```

You should see files/folders like:

```txt
app/
data/
knowledge-base/
prompts/
evals/
tests/
ui/
requirements.txt
run.py
.env.example
.gitignore
README.md
```

On Windows PowerShell:

```powershell
Get-Location
dir
```

---

## Step 2 — Create and Activate Virtual Environment

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\.venv\Scripts\Activate.ps1
```

### Git Bash / Linux / macOS

```bash
python -m venv .venv
source .venv/bin/activate
```

---

## Step 3 — Install Dependencies

Run:

```bash
pip install -r requirements.txt
```

If pip is outdated:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

## Step 4 — Confirm `.env` Exists Locally

You need a local `.env` for LLM mode.

If `.env` does not exist:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Then edit `.env`.

For Groq via OpenAI-compatible API:

```env
OPENAI_API_KEY=your_new_rotated_groq_key_here
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_MODEL=llama-3.3-70b-versatile
LLM_TEMPERATURE=0
LLM_SEED=42
```

Important:

```txt
Do not paste the real key into .env.example.
Do not commit .env.
If a key was exposed earlier, rotate it in Groq console before using it again.
```

---

## Step 5 — Confirm `.env` Is Ignored

Run:

```bash
git check-ignore -v .env
```

Expected:
- It should show a `.gitignore` rule.

Then run:

```bash
git ls-files .env
```

Expected:
- It should print nothing.

If `git ls-files .env` prints `.env`, remove it from Git tracking:

```bash
git rm --cached .env
```

Then make sure `.gitignore` contains:

```gitignore
.env
*.env
.env.local
```

---

## Step 6 — Run Secret Safety Check

If `scripts/check_secrets.py` exists, run:

```bash
python scripts/check_secrets.py
```

Expected:
- No real keys detected in committed files.
- `.env` is ignored or not tracked.

If this script flags a real key in `.env.example`, fix `.env.example` so it contains only:

```env
OPENAI_API_KEY=your_api_key_here
```

---

## Step 7 — Start the FastAPI Server

Run:

```bash
python run.py
```

Expected output should look similar to:

```txt
Uvicorn running on http://0.0.0.0:8000
```

Keep this terminal open.

---

## Step 8 — Open the Local API Link

Open this in your browser:

```txt
http://localhost:8000/docs
```

This is your Swagger UI.

Also check:

```txt
http://localhost:8000/health
```

Expected:

```json
{
  "status": "ok",
  "service": "us-delivery-ai-support",
  "version": "0.1.0"
}
```

Dataset status link:

```txt
http://localhost:8000/dataset/status
```

If official data is missing, it may show:

```json
{
  "ready": false,
  "message": "Dataset is not ready..."
}
```

That is acceptable.

Ticket triage should still be testable because it accepts a new incoming ticket directly.

---

## Step 9 — Raise a Ticket Through Swagger UI

Open:

```txt
http://localhost:8000/docs
```

Find:

```txt
POST /triage
```

Click:

```txt
Try it out
```

Use this request body:

```json
{
  "subject": "SSO login outage after SAML update",
  "body": "All users are unable to log in after we changed the SAML configuration this morning. This is blocking production access for our team."
}
```

Click:

```txt
Execute
```

Expected response shape:

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
    "match_reason": "No knowledge-base documents were available for retrieval.",
    "confidence": 0.0
  },
  "recommended_team": "...",
  "draft_first_response": "...",
  "retrieved_docs": [],
  "prompt_version": "triage_v1",
  "deterministic": true
}
```

If KB docs are missing, `known_issue_match.matched` should be `false`.

This is correct. Do not force a known issue match without KB docs.

---

## Step 10 — Raise a Ticket Using curl

Open a second terminal while the server is running.

Run:

```bash
curl -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "SSO login outage after SAML update",
    "body": "All users are unable to log in after we changed the SAML configuration this morning. This is blocking production access for our team."
  }'
```

Expected:
- HTTP 200
- JSON response
- `urgency_tier` one of `P1`, `P2`, `P3`, `P4`
- `draft_first_response` present
- `known_issue_match.matched=false` if KB unavailable

---

## Step 11 — Raise a Ticket Using Windows PowerShell

PowerShell command:

```powershell
$body = @{
  subject = "SSO login outage after SAML update"
  body = "All users are unable to log in after we changed the SAML configuration this morning. This is blocking production access for our team."
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/triage" -Method Post -Body $body -ContentType "application/json"
```

Expected:
- Structured JSON response.

---

## Step 12 — Test Raw Free-Text Ticket Input

Swagger or curl body:

```json
{
  "text": "Customer reports duplicate invoice charges for this month and needs billing team review before finance close."
}
```

Curl:

```bash
curl -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Customer reports duplicate invoice charges for this month and needs billing team review before finance close."
  }'
```

Expected:
- Valid response.
- Product area and issue category non-empty.
- Urgency likely P2/P3/P4 depending implementation.
- Draft response present.

---

## Step 13 — Test Ambiguous Ticket

Use:

```json
{
  "text": "It is broken. Please fix ASAP."
}
```

Expected:
- No crash.
- Urgency is still valid P1/P2/P3/P4.
- Reasoning should mention ambiguity or insufficient information.
- Draft response should ask for more details.

---

## Step 14 — Test PII Redaction

Use:

```json
{
  "subject": "Login issue for john@example.com",
  "body": "Please call me at 9876543210. Users cannot access the dashboard."
}
```

Expected:
- The prompt sent to LLM should internally redact PII.
- The response should not expose the raw phone/email unnecessarily.

If tests exist, run:

```bash
pytest tests/test_pii.py tests/test_triage_agent.py
```

---

## Step 15 — Run Automated Tests for Ticket Raising

Run:

```bash
pytest tests/test_api.py tests/test_triage_agent.py tests/test_pii.py
```

Then:

```bash
python -m compileall app tests
```

If all pass, the ticket-raising flow is working.

---

## Step 16 — If `/triage` Fails Because LLM Key Is Missing

Expected behavior:
- The app should use fallback triage if implemented.
- If fallback is not implemented or broken, Claude Code must fix `TicketTriageAgent`.

Required fallback behavior:

```txt
If LLM is not configured:
- Return valid TicketTriageResponse.
- Clearly mention local fallback in reasoning.
- Use simple urgency rules.
- Do not crash.
```

Simple urgency fallback:

```txt
P1: outage, all users, production down, data loss, security
P2: blocked, broken, urgent, major customer/account impact
P3: normal issue with limited scope
P4: documentation, how-to, minor question
```

---

## Step 17 — If `/triage` Fails Because KB Is Missing

This should not happen.

Claude Code must ensure:

```txt
Missing KB docs should not crash ticket triage.
Retrieved docs should be [].
known_issue_match.matched should be false.
Response should remain valid.
```

Fix `app/triage_agent.py` or `app/retrieval.py` if missing KB crashes.

---

## Step 18 — If `/health` Works but `/docs` Does Not

Check FastAPI installation:

```bash
pip show fastapi uvicorn
```

Reinstall if needed:

```bash
pip install -r requirements.txt
```

Restart:

```bash
python run.py
```

Open:

```txt
http://127.0.0.1:8000/docs
```

If `localhost` fails, use `127.0.0.1`.

---

## Step 19 — If Port 8000 Is Already in Use

Use another port if `run.py` supports `APP_PORT`.

In `.env`:

```env
APP_PORT=8001
```

Then:

```bash
python run.py
```

Open:

```txt
http://localhost:8001/docs
```

Or kill process on port 8000.

Windows PowerShell:

```powershell
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

---

## Step 20 — Final Confirmation Checklist

Before saying ticket raising works, confirm:

```txt
[ ] python run.py starts server
[ ] http://localhost:8000/health returns ok
[ ] http://localhost:8000/docs opens
[ ] POST /triage accepts subject/body
[ ] POST /triage accepts raw text
[ ] Response includes urgency_tier
[ ] Response includes recommended_team
[ ] Response includes draft_first_response
[ ] Missing KB does not crash
[ ] known_issue_match is false when no KB docs are available
[ ] No fake official dataset was created
[ ] .env is not tracked
```

---

## The Link You Should Use

After starting the server, use this:

```txt
http://localhost:8000/docs
```

If your app runs on port 8001:

```txt
http://localhost:8001/docs
```

This link works only on your machine while `python run.py` is running.

---

## Expected Ticket Raising Demo Input

Use this for Loom/demo:

```json
{
  "subject": "SSO login outage after SAML update",
  "body": "All users are unable to log in after we changed the SAML configuration this morning. This is blocking production access for our team."
}
```

Expected outcome:

```txt
Valid structured triage output.
Urgency tier likely P1 or P2.
Known issue false if KB docs unavailable.
Recommended team present.
Draft first response present.
```

---

## Final Instruction to Claude Code

Run the project and verify the ticket triage flow end-to-end.

If any of these fail:

```txt
/health
/docs
POST /triage with subject/body
POST /triage with raw text
missing KB graceful behavior
missing LLM fallback behavior
```

fix the implementation until the checks pass.

Do not create fake official data to make this work.
