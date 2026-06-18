"""Knowledge-base Markdown loading utilities."""

from __future__ import annotations

import re
from pathlib import Path

from app.config import Settings, get_settings
from app.schemas import KBDocument


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class KnowledgeBaseError(Exception):
    """Base exception for knowledge-base loading errors."""


class MissingKnowledgeBaseError(KnowledgeBaseError):
    """Raised when the knowledge-base directory is missing."""


class EmptyKnowledgeBaseError(KnowledgeBaseError):
    """Raised when no usable Markdown docs are found."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def discover_markdown_files(kb_dir: Path) -> list[Path]:
    """Return sorted Markdown files under the KB directory.

    Raises:
        MissingKnowledgeBaseError: if *kb_dir* does not exist or is not a directory.
    """
    if not kb_dir.exists() or not kb_dir.is_dir():
        raise MissingKnowledgeBaseError(
            f"Knowledge-base directory not found: {kb_dir}"
        )

    md_files: list[Path] = []
    for path in kb_dir.rglob("*.md"):
        # Skip hidden files/directories (any path component starting with '.')
        if any(part.startswith(".") for part in path.relative_to(kb_dir).parts):
            continue
        md_files.append(path)

    # Sort by relative path for deterministic ordering
    md_files.sort(key=lambda p: p.relative_to(kb_dir).as_posix())
    return md_files


def extract_title(content: str, fallback: str) -> str:
    """Extract first Markdown H1/H2 title or fallback to readable file stem.

    Examples:
        ``extract_title("# Login Issues\\nDetails", "login-issues")``
        → ``"Login Issues"``

        ``extract_title("No heading here", "billing_refunds")``
        → ``"Billing Refunds"``
    """
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            return stripped.lstrip("#").strip()
        if stripped.startswith("# "):
            return stripped.lstrip("#").strip()

    # Convert stem like "sso-login-errors" or "billing_refunds" to readable title
    readable = fallback.replace("-", " ").replace("_", " ")
    return readable.title()


def make_doc_id(path: Path, kb_dir: Path) -> str:
    """Create stable doc ID from relative path.

    Example::

        knowledge-base/troubleshooting/sso-login.md
        → troubleshooting__sso-login
    """
    relative = path.relative_to(kb_dir).with_suffix("")
    doc_id = relative.as_posix().replace("/", "__").replace(" ", "-").lower()
    return doc_id


def infer_category(path: Path, kb_dir: Path) -> str | None:
    """Infer top-level category folder under KB dir.

    Examples::

        knowledge-base/billing/refunds.md → "billing"
        knowledge-base/root-doc.md → None
    """
    relative = path.relative_to(kb_dir)
    parts = relative.parts
    if len(parts) > 1:
        return parts[0].lower()
    return None


def load_kb_document(path: Path, kb_dir: Path) -> KBDocument:
    """Load one Markdown file into a KBDocument.

    Raises:
        EmptyKnowledgeBaseError: if the file content is empty after stripping.
    """
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        raise EmptyKnowledgeBaseError(
            f"Knowledge-base document is empty: {path}"
        )

    title = extract_title(raw, path.stem)
    doc_id = make_doc_id(path, kb_dir)
    category = infer_category(path, kb_dir)
    relative_posix = path.relative_to(kb_dir).as_posix()

    return KBDocument(
        doc_id=doc_id,
        title=title,
        path=relative_posix,
        content=raw,
        category=category,
    )


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------


def load_knowledge_base(
    settings: Settings | None = None,
    strict: bool = False,
) -> list[KBDocument]:
    """Load all usable Markdown KB docs.

    Args:
        settings: Application settings. Uses cached defaults if ``None``.
        strict: If ``True``, raise on any empty doc. If ``False``, skip them.

    Raises:
        MissingKnowledgeBaseError: if the KB directory is missing.
        EmptyKnowledgeBaseError: if no usable docs are found after filtering.
    """
    if settings is None:
        settings = get_settings()

    md_files = discover_markdown_files(settings.kb_dir)

    if not md_files:
        raise EmptyKnowledgeBaseError(
            f"No Markdown documents found in knowledge-base: {settings.kb_dir}"
        )

    docs: list[KBDocument] = []
    for md_path in md_files:
        try:
            doc = load_kb_document(md_path, settings.kb_dir)
            docs.append(doc)
        except EmptyKnowledgeBaseError:
            if strict:
                raise
            # Non-strict: skip empty docs silently

    if not docs:
        raise EmptyKnowledgeBaseError(
            "All Markdown documents in the knowledge-base are empty."
        )

    return docs
