# Deploying the UI on Streamlit Community Cloud

The Streamlit UI (`ui/streamlit_app.py`) runs the triage / account / eval logic
**in-process** — it imports the `app` package directly and does not need the
FastAPI server running. That makes it self-contained and deployable to
[Streamlit Community Cloud](https://share.streamlit.io) on its own.

## What is already wired for deployment

- `ui/streamlit_app.py` inserts the repo root into `sys.path`, so `import app`
  works when the entry script lives in `ui/`.
- `bridge_secrets_to_env()` copies `st.secrets` into environment variables
  before settings load, so the same `app.config.Settings` path works locally
  (`.env`) and on the cloud (dashboard secrets). It never overwrites an
  existing env var.
- `requirements.txt` already lists `streamlit` and every runtime dependency.
- `.streamlit/secrets.toml` is gitignored; `.streamlit/secrets.toml.example`
  shows the keys to set.

## Steps

1. **Push the repo to GitHub** (the local `.env` stays untracked — verified by
   `git ls-files .env` printing nothing).

2. Go to https://share.streamlit.io and click **New app**.

3. Configure:
   - **Repository:** your GitHub repo
   - **Branch:** `main`
   - **Main file path:** `ui/streamlit_app.py`

4. Open **Advanced settings -> Secrets** and paste the contents of
   `.streamlit/secrets.toml.example`, replacing the placeholders with your
   **real, rotated** key:

   ```toml
   OPENAI_API_KEY = "your_rotated_key_here"
   OPENAI_BASE_URL = "https://api.groq.com/openai/v1"
   OPENAI_MODEL = "llama-3.3-70b-versatile"
   LLM_TEMPERATURE = "0"
   LLM_SEED = "42"
   ```

5. Click **Deploy**. Streamlit gives you a public URL like
   `https://<your-app>.streamlit.app`.

## Behavior on the cloud

- The official dataset is **not** committed, so Dataset Status shows
  "not ready" and the TAM Account Brief tab fails gracefully — this is
  intentional and honest.
- **Ticket Triage works fully**, because it accepts a ticket directly from the
  UI. With the key set it uses the LLM; without it, the deterministic local
  fallback is used.
- No secret is ever displayed; the sidebar only shows "LLM API key: configured".

## Security reminder

If the key was ever shown in a terminal, log, or screenshot, **rotate it** in
the provider console before deploying. Removing it from a file does not undo
prior exposure.
