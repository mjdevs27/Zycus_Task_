"""Config smoke test — verify LLM configuration is loaded (without exposing it).

Confirms that app.config resolves the OpenAI/Groq settings from .env (or already
present environment variables) regardless of the current working directory.
Never prints the API key.

Run:
    python scripts/smoke_test_config.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env", override=False)

from app.config import get_settings  # noqa: E402


def main() -> None:
    settings = get_settings()

    # Booleans / non-secret values only — never the key itself.
    print("OPENAI_API_KEY loaded:", bool(settings.openai_api_key))
    print("OPENAI_BASE_URL loaded:", bool(settings.openai_base_url))
    print("OPENAI_BASE_URL:", settings.openai_base_url or "(OpenAI default)")
    print("OPENAI_MODEL:", settings.openai_model)
    print("APP_ENV:", settings.app_env)

    if not settings.openai_model:
        print("CONFIG SMOKE FAILED: no model configured")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
