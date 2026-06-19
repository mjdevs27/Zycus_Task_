"""Direct triage smoke test (no server, no official dataset required).

Instantiates the triage agent and runs the canonical SSO-outage ticket through
it, printing the structured result. Exits 0 when the response contains an
urgency tier and a draft first response, 1 otherwise. Never prints the API key.

Run:
    python scripts/smoke_test_triage.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load local .env if present; config also loads it, this just makes the script
# self-sufficient when run directly. Never overrides real environment values.
load_dotenv(PROJECT_ROOT / ".env", override=False)

from app.schemas import TicketTriageRequest  # noqa: E402
from app.triage_agent import TicketTriageAgent  # noqa: E402


def main() -> None:
    request = TicketTriageRequest(
        subject="SSO login outage after SAML configuration update",
        body=(
            "All users are unable to log in after we changed the SAML "
            "configuration this morning. This is blocking production access for "
            "the customer's team, and they need urgent support to restore access."
        ),
    )

    result = TicketTriageAgent().triage(request)
    data = result.model_dump()

    # Print the result without exposing any secret (the response carries none).
    print(json.dumps(data, indent=2, default=str))

    if not data.get("urgency_tier") or not data.get("draft_first_response"):
        print("SMOKE TEST FAILED: missing urgency_tier or draft_first_response")
        raise SystemExit(1)

    print(
        f"SMOKE TEST PASSED: urgency={data['urgency_tier']} "
        f"team={data.get('recommended_team')} "
        f"known_issue_match={data['known_issue_match']['matched']} "
        f"deterministic={data.get('deterministic')}"
    )


if __name__ == "__main__":
    main()
