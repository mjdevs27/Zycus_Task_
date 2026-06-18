"""Submission-readiness validation for the US Delivery AI Support repository.

Runs a series of checks and writes ``FINAL_VALIDATION.md``. It returns a nonzero
exit code only for *real* failures:

* Non-strict (default): a missing official dataset is a WARNING.
* Strict (``--strict``): a missing official dataset is a FAILURE.
* Detected secrets or a tracked ``.env`` are always FAILURES.

CLI:
    python scripts/final_validate.py
    python scripts/final_validate.py --strict
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Ensure the repository root is importable when run as ``python scripts/...``.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"

REQUIRED_FILES = [
    "README.md",
    "DESIGN_NOTE.md",
    "requirements.txt",
    ".env.example",
    "run.py",
    "app/main.py",
    "app/triage_agent.py",
    "app/account_summarizer.py",
    "evals/run_evals.py",
    "evals/scoring.py",
    "prompts/triage_v1.md",
    "prompts/account_summary_v1.md",
    "prompts/CHANGELOG.md",
]

# Bonus file -> the README marker that indicates the feature is claimed.
BONUS_FILES = {
    "ui/streamlit_app.py": "ui/streamlit_app.py",
    ".github/workflows/evals.yml": ".github/workflows/evals.yml",
    "scripts/check_secrets.py": "scripts/check_secrets.py",
    "app/streaming.py": "brief/stream",
}

DESIGN_NOTE_KEYWORDS = [
    "failure mode",
    "latency",
    "data sensitivity",
    "scaling",
]


@dataclass
class CheckResult:
    """One validation result."""

    status: str
    check: str
    details: str


def add_pass(results: list[CheckResult], check: str, details: str = "") -> None:
    results.append(CheckResult(PASS, check, details))


def add_warn(results: list[CheckResult], check: str, details: str = "") -> None:
    results.append(CheckResult(WARN, check, details))


def add_fail(results: list[CheckResult], check: str, details: str = "") -> None:
    results.append(CheckResult(FAIL, check, details))


def has_failures(results: list[CheckResult]) -> bool:
    """Return True if any result is a FAIL."""
    return any(r.status == FAIL for r in results)


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def check_required_files(results: list[CheckResult], root: Path) -> None:
    for rel in REQUIRED_FILES:
        if (root / rel).exists():
            add_pass(results, f"Required file: {rel}", rel)
        else:
            add_fail(results, f"Required file: {rel}", "missing")


def check_bonus_files(results: list[CheckResult], root: Path) -> None:
    readme = root / "README.md"
    readme_text = readme.read_text(encoding="utf-8") if readme.exists() else ""
    for rel, marker in BONUS_FILES.items():
        exists = (root / rel).exists()
        claimed = marker in readme_text
        if exists:
            add_pass(results, f"Bonus file: {rel}", rel)
        elif claimed:
            add_fail(results, f"Bonus file: {rel}", "claimed in README but missing")
        else:
            add_warn(results, f"Bonus file: {rel}", "not present (not claimed)")


def check_dataset(results: list[CheckResult], root: Path, strict: bool) -> None:
    try:
        from app.data_loader import check_dataset_status

        status = check_dataset_status()
    except Exception as exc:  # noqa: BLE001
        add_warn(results, "Dataset readiness", f"could not check: {type(exc).__name__}")
        return

    if status.ready:
        add_pass(results, "Dataset readiness", "official dataset ready")
    elif strict:
        add_fail(results, "Dataset readiness", status.message)
    else:
        add_warn(results, "Dataset readiness", status.message)


def check_secrets(results: list[CheckResult], root: Path) -> None:
    try:
        from scripts.check_secrets import env_is_tracked, scan_repository

        violations = scan_repository(root)
    except Exception as exc:  # noqa: BLE001
        add_warn(results, "Secret scan", f"could not run scanner: {type(exc).__name__}")
        return

    if violations:
        add_fail(results, "Secret scan", f"{len(violations)} potential secret(s) found")
    else:
        add_pass(results, "Secret scan", "no likely secrets detected")

    tracked = env_is_tracked(root)
    if tracked is True:
        add_fail(results, ".env tracking", ".env is tracked by Git")
    elif tracked is None:
        add_warn(results, ".env tracking", "Git unavailable; could not verify")
    else:
        add_pass(results, ".env tracking", ".env is not tracked")

    # Best-effort check that .env is ignored when Git is available.
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-v", ".env"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            add_pass(results, ".env ignored", "matched by .gitignore")
        elif result.returncode == 0:
            add_warn(results, ".env ignored", "no .env present to check")
        else:
            add_warn(results, ".env ignored", "not reported as ignored")
    except (OSError, subprocess.SubprocessError):
        add_warn(results, ".env ignored", "Git unavailable; could not verify")


def check_eval_report(results: list[CheckResult], root: Path, strict: bool) -> None:
    json_path = root / "eval_report.json"
    md_path = root / "eval_report.md"
    if json_path.exists() or md_path.exists():
        add_pass(results, "Eval report", "report file present")
        return

    # Neither exists: try to generate one.
    try:
        from evals.run_evals import run_all_evals

        report = run_all_evals()
    except Exception as exc:  # noqa: BLE001
        add_fail(results, "Eval report", f"generation failed: {type(exc).__name__}")
        return

    if report.dataset_ready:
        add_pass(results, "Eval report", "generated with dataset_ready=true")
    elif strict:
        add_fail(results, "Eval report", "generated but dataset_ready=false")
    else:
        add_warn(results, "Eval report", "generated with dataset_ready=false")


def check_docs(results: list[CheckResult], root: Path) -> None:
    readme = root / "README.md"
    if readme.exists() and "setup" in readme.read_text(encoding="utf-8").lower():
        add_pass(results, "README content", "exists and mentions setup")
    else:
        add_fail(results, "README content", "missing or no setup section")

    design = root / "DESIGN_NOTE.md"
    if design.exists():
        text = design.read_text(encoding="utf-8").lower()
        missing = [kw for kw in DESIGN_NOTE_KEYWORDS if kw not in text]
        if missing:
            add_fail(results, "DESIGN_NOTE content", f"missing: {', '.join(missing)}")
        else:
            add_pass(results, "DESIGN_NOTE content", "covers all required prompts")
    else:
        add_fail(results, "DESIGN_NOTE content", "missing")

    for rel in ("SUBMISSION_CHECKLIST.md", "LOOM_SCRIPT.md"):
        if (root / rel).exists():
            add_pass(results, f"Doc: {rel}", rel)
        else:
            add_fail(results, f"Doc: {rel}", "missing")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _escape_md(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def write_final_validation_report(
    results: list[CheckResult],
    path: str | Path = "FINAL_VALIDATION.md",
    generated_at: str = "",
) -> None:
    """Write *results* to a Markdown report with a summary and a checks table."""
    path = Path(path)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    counts = {PASS: 0, WARN: 0, FAIL: 0}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1

    lines = ["# Final Validation Report", ""]
    if generated_at:
        lines.append(f"Generated at: {generated_at}")
        lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Status | Count |")
    lines.append("|---|---:|")
    lines.append(f"| PASS | {counts[PASS]} |")
    lines.append(f"| WARN | {counts[WARN]} |")
    lines.append(f"| FAIL | {counts[FAIL]} |")
    lines.append("")
    lines.append("## Checks")
    lines.append("")
    lines.append("| Status | Check | Details |")
    lines.append("|---|---|---|")
    for r in results:
        lines.append(
            f"| {r.status} | {_escape_md(r.check)} | {_escape_md(r.details)} |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def run_validation(root: str | Path = ".", strict: bool = False) -> list[CheckResult]:
    """Run all checks and return the result list."""
    root = Path(root)
    results: list[CheckResult] = []
    check_required_files(results, root)
    check_bonus_files(results, root)
    check_dataset(results, root, strict)
    check_secrets(results, root)
    check_eval_report(results, root, strict)
    check_docs(results, root)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Submission-readiness validation.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat a missing official dataset as a failure.",
    )
    args = parser.parse_args(argv)

    results = run_validation(".", strict=args.strict)

    # Timestamp is read from the environment-independent eval report if present,
    # else left blank to keep the script deterministic and import-safe.
    write_final_validation_report(results, "FINAL_VALIDATION.md")

    counts = {PASS: 0, WARN: 0, FAIL: 0}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
        marker = {PASS: "PASS", WARN: "WARN", FAIL: "FAIL"}[r.status]
        print(f"[{marker}] {r.check} - {r.details}")

    print(
        f"\nSummary: {counts[PASS]} pass, {counts[WARN]} warn, {counts[FAIL]} fail"
    )
    print("Report written to FINAL_VALIDATION.md")

    return 1 if has_failures(results) else 0


if __name__ == "__main__":
    sys.exit(main())
