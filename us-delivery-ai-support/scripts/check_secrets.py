"""Local secret scanner for the US Delivery AI Support repository.

Detects likely leaked API keys before submission and ensures ``.env`` is not
tracked by Git. It never prints a full secret — only a redacted preview.

CLI:
    python scripts/check_secrets.py

Exit codes:
    0  clean
    1  a likely secret was found, or ``.env`` is tracked by Git
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Directory fragments and file suffixes that are never scanned.
IGNORED_DIR_PARTS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "ENV",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "node_modules",
    ".graphify",
    "graphify-out",
}
IGNORED_SUFFIXES = {
    ".pyc",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pdf",
    ".zip",
    ".gz",
    ".tar",
    ".ico",
    ".woff",
    ".woff2",
}

# Values that are explicitly allowed in committed files (e.g. .env.example).
ALLOWED_PLACEHOLDERS = {
    "your_api_key_here",
    "your_groq_key_here",
    "sk_your_openai_key_here",
    "gsk_your_groq_key_here",
    "changeme",
    "placeholder",
    "<your-key-here>",
}

# Obvious documentation/test dummy keys are an alphabet walk; no real key
# contains a long run of sequential letters. This lets docs and the scanner's
# own tests show example keys without tripping the scan.
_ALPHABET_WALK = "abcdefghijklmnopqrstuvwxyz"
_EXAMPLE_MARKERS = ("abcdefghijklmnop",)

# High-entropy provider key shapes. ``sk-proj-`` is matched by the ``sk-`` rule.
_KEY_PATTERNS = [
    ("Groq API key (gsk_)", re.compile(r"gsk_[^\s\"']{20,}")),
    ("OpenAI API key (sk-)", re.compile(r"sk-[A-Za-z0-9_\-]{20,}")),
]

# Assignment patterns like OPENAI_API_KEY=<value>.
_ASSIGNMENT_RE = re.compile(
    r"(?P<name>OPENAI_API_KEY|GROQ_API_KEY|ANTHROPIC_API_KEY)\s*=\s*(?P<value>\S+)"
)

MAX_SCAN_BYTES = 1_000_000  # Skip very large files; secrets live in small text files.

# Inline marker that allow-lists a single line (e.g. a test fixture holding a
# deliberately fake key). Mirrors the detect-secrets "pragma: allowlist secret".
ALLOWLIST_MARKER = "allowlist-secret"


@dataclass
class Violation:
    """One likely-secret finding."""

    file: str
    reason: str
    preview: str


def redact_secret(secret: str) -> str:
    """Return a redacted preview that keeps only a short prefix and suffix."""
    secret = secret.strip().strip("\"'")
    if len(secret) <= 8:
        return (secret[:2] if secret else "") + "****"
    prefix = secret[:4]
    suffix = secret[-4:]
    return f"{prefix}****{suffix}"


def _normalize_value(value: str) -> str:
    """Strip surrounding quotes and trailing source punctuation from a value."""
    return value.strip().strip("\"'").rstrip("\"').,;")


def is_placeholder_value(value: str) -> bool:
    """Return True if *value* is an allowed placeholder rather than a real key."""
    cleaned = _normalize_value(value)
    return cleaned in ALLOWED_PLACEHOLDERS or cleaned == ""


def looks_like_example_key(token: str) -> bool:
    """Return True for obvious documentation/test dummy keys (alphabet walks)."""
    lowered = token.lower()
    if any(marker in lowered for marker in _EXAMPLE_MARKERS):
        return True
    return _ALPHABET_WALK[:12] in lowered


def looks_like_real_value(value: str) -> bool:
    """Return True if an assignment value looks like a real key, not prose.

    Real keys are long and mix letters with digits/symbols. This avoids flagging
    documentation prose such as ``OPENAI_API_KEY= with non-placeholder value``.
    """
    cleaned = _normalize_value(value)
    if len(cleaned) < 16:
        return False
    if looks_like_example_key(cleaned):
        return False
    has_digit = any(ch.isdigit() for ch in cleaned)
    has_alpha = any(ch.isalpha() for ch in cleaned)
    return has_digit and has_alpha


def is_ignored_path(path: str | Path) -> bool:
    """Return True if *path* is excluded from content scanning.

    Excludes binary suffixes, well-known generated directories, and the local
    ``.env`` secret store (``.env`` / ``.env.*`` but never ``.env.example``).
    The ``.env`` files are gitignored and covered separately by the tracking
    guard, so scanning their (intentionally real) local key is not a leak.
    """
    p = Path(path)
    if p.suffix.lower() in IGNORED_SUFFIXES:
        return True
    name = p.name
    if name != ".env.example" and (name == ".env" or name.startswith(".env.") or name.endswith(".env")):
        return True
    return any(part in IGNORED_DIR_PARTS for part in p.parts)


def scan_text(text: str) -> list[tuple[str, str]]:
    """Scan *text* for likely secrets.

    Returns a list of ``(reason, matched_secret)`` tuples. Placeholder values in
    ``NAME=value`` assignments are allowed and produce no finding.
    """
    findings: list[tuple[str, str]] = []

    for assignment in _ASSIGNMENT_RE.finditer(text):
        name = assignment.group("name")
        value = assignment.group("value")
        if is_placeholder_value(value):
            continue
        # Only flag assignments whose value actually looks like a real key, so
        # documentation prose and example values do not produce false positives.
        if looks_like_real_value(value):
            findings.append(
                (f"{name} set to a non-placeholder value", _normalize_value(value))
            )

    for reason, pattern in _KEY_PATTERNS:
        for match in pattern.finditer(text):
            secret = match.group(0)
            if is_placeholder_value(secret) or looks_like_example_key(secret):
                continue
            findings.append((reason, secret))

    return findings


def scan_file(path: Path) -> list[Violation]:
    """Scan a single file, returning any violations found."""
    if is_ignored_path(path):
        return []
    try:
        if path.stat().st_size > MAX_SCAN_BYTES:
            return []
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []  # Binary / unreadable files are skipped, not failed.

    violations: list[Violation] = []
    seen: set[tuple[str, str]] = set()
    # Scan line-by-line so a single line can be allow-listed with a marker.
    for line in text.splitlines():
        if ALLOWLIST_MARKER in line:
            continue
        for reason, secret in scan_text(line):
            key = (reason, secret)
            if key in seen:
                continue
            seen.add(key)
            violations.append(
                Violation(file=str(path), reason=reason, preview=redact_secret(secret))
            )
    return violations


def scan_repository(root: str | Path = ".") -> list[Violation]:
    """Recursively scan the repository for likely secrets."""
    root = Path(root)
    violations: list[Violation] = []
    for path in root.rglob("*"):
        if not path.is_file() or is_ignored_path(path):
            continue
        violations.extend(scan_file(path))
    return violations


def env_is_tracked(root: str | Path = ".") -> bool | None:
    """Return True/False if ``.env`` is tracked, or None if Git is unavailable."""
    try:
        result = subprocess.run(
            ["git", "ls-files", ".env"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return ".env" in result.stdout.split()


def main(root: str | Path = ".") -> int:
    """Run the scan and the ``.env`` tracking guard; return an exit code."""
    violations = scan_repository(root)
    failed = False

    if violations:
        failed = True
        print("Potential secrets detected:")
        for violation in violations:
            print(f"  - {violation.file}: {violation.reason} [{violation.preview}]")
    else:
        print("No likely secrets detected.")

    tracked = env_is_tracked(root)
    if tracked is True:
        failed = True
        print(".env is tracked by Git. Remove it with: git rm --cached .env")
    elif tracked is None:
        print("Warning: could not verify .env tracking (Git unavailable).")
    else:
        print(".env is not tracked by Git.")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
