"""Tests for app.kb_loader — knowledge-base Markdown loading."""

from pathlib import Path

import pytest

from app.config import Settings
from app.kb_loader import (
    EmptyKnowledgeBaseError,
    MissingKnowledgeBaseError,
    discover_markdown_files,
    extract_title,
    infer_category,
    load_knowledge_base,
    make_doc_id,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(tmp_path: Path) -> Settings:
    """Create Settings with KB dir under tmp_path."""
    return Settings(
        KB_DIR=tmp_path / "knowledge-base",
        TICKETS_FILE=tmp_path / "data" / "tickets.json",
        ACCOUNTS_FILE=tmp_path / "data" / "accounts.json",
    )


# ---------------------------------------------------------------------------
# discover_markdown_files
# ---------------------------------------------------------------------------


def test_missing_kb_dir_raises(tmp_path: Path):
    with pytest.raises(MissingKnowledgeBaseError):
        discover_markdown_files(tmp_path / "missing")


def test_empty_kb_dir_returns_empty_list(tmp_path: Path):
    kb_dir = tmp_path / "knowledge-base"
    kb_dir.mkdir()
    files = discover_markdown_files(kb_dir)
    assert files == []


def test_discover_ignores_hidden_files(tmp_path: Path):
    kb_dir = tmp_path / "knowledge-base"
    kb_dir.mkdir()
    (kb_dir / ".hidden.md").write_text("# Hidden", encoding="utf-8")
    (kb_dir / "visible.md").write_text("# Visible", encoding="utf-8")
    files = discover_markdown_files(kb_dir)
    assert len(files) == 1
    assert files[0].name == "visible.md"


# ---------------------------------------------------------------------------
# extract_title
# ---------------------------------------------------------------------------


def test_extract_title_from_h1():
    assert extract_title("# Login Issues\nDetails", "login-issues") == "Login Issues"


def test_extract_title_from_h2():
    assert extract_title("## Billing FAQ\nContent", "billing") == "Billing FAQ"


def test_extract_title_uses_fallback():
    assert extract_title("No heading here", "billing_refunds") == "Billing Refunds"


def test_extract_title_fallback_with_hyphens():
    assert extract_title("No heading", "sso-login-errors") == "Sso Login Errors"


# ---------------------------------------------------------------------------
# make_doc_id
# ---------------------------------------------------------------------------


def test_make_doc_id_nested(tmp_path: Path):
    kb_dir = tmp_path / "knowledge-base"
    path = kb_dir / "troubleshooting" / "sso-login.md"
    assert make_doc_id(path, kb_dir) == "troubleshooting__sso-login"


def test_make_doc_id_root_level(tmp_path: Path):
    kb_dir = tmp_path / "knowledge-base"
    path = kb_dir / "overview.md"
    assert make_doc_id(path, kb_dir) == "overview"


# ---------------------------------------------------------------------------
# infer_category
# ---------------------------------------------------------------------------


def test_infer_category_nested(tmp_path: Path):
    kb_dir = tmp_path / "knowledge-base"
    path = kb_dir / "billing" / "refunds.md"
    assert infer_category(path, kb_dir) == "billing"


def test_infer_category_root_returns_none(tmp_path: Path):
    kb_dir = tmp_path / "knowledge-base"
    path = kb_dir / "root-doc.md"
    assert infer_category(path, kb_dir) is None


# ---------------------------------------------------------------------------
# load_knowledge_base
# ---------------------------------------------------------------------------


def test_load_knowledge_base_loads_markdown(tmp_path: Path):
    kb_dir = tmp_path / "knowledge-base"
    (kb_dir / "troubleshooting").mkdir(parents=True)
    (kb_dir / "troubleshooting" / "sso.md").write_text(
        "# SSO Login\nKnown issue details.", encoding="utf-8"
    )

    settings = _make_settings(tmp_path)
    # Override kb_dir since _make_settings uses tmp_path / "knowledge-base"
    docs = load_knowledge_base(settings=settings)
    assert len(docs) == 1
    assert docs[0].title == "SSO Login"
    assert docs[0].category == "troubleshooting"


def test_load_knowledge_base_empty_dir_raises(tmp_path: Path):
    kb_dir = tmp_path / "knowledge-base"
    kb_dir.mkdir()
    settings = _make_settings(tmp_path)
    with pytest.raises(EmptyKnowledgeBaseError):
        load_knowledge_base(settings=settings)


def test_load_knowledge_base_skips_empty_non_strict(tmp_path: Path):
    kb_dir = tmp_path / "knowledge-base"
    kb_dir.mkdir()
    (kb_dir / "empty.md").write_text("", encoding="utf-8")
    (kb_dir / "real.md").write_text("# Real Doc\nContent here.", encoding="utf-8")
    settings = _make_settings(tmp_path)
    docs = load_knowledge_base(settings=settings, strict=False)
    assert len(docs) == 1
    assert docs[0].title == "Real Doc"


def test_load_knowledge_base_raises_strict_on_empty(tmp_path: Path):
    kb_dir = tmp_path / "knowledge-base"
    kb_dir.mkdir()
    (kb_dir / "empty.md").write_text("", encoding="utf-8")
    (kb_dir / "real.md").write_text("# Real Doc\nContent here.", encoding="utf-8")
    settings = _make_settings(tmp_path)
    with pytest.raises(EmptyKnowledgeBaseError):
        load_knowledge_base(settings=settings, strict=True)


def test_load_knowledge_base_multiple_docs_sorted(tmp_path: Path):
    kb_dir = tmp_path / "knowledge-base"
    kb_dir.mkdir()
    (kb_dir / "zeta.md").write_text("# Zeta\nContent.", encoding="utf-8")
    (kb_dir / "alpha.md").write_text("# Alpha\nContent.", encoding="utf-8")
    settings = _make_settings(tmp_path)
    docs = load_knowledge_base(settings=settings)
    assert len(docs) == 2
    assert docs[0].title == "Alpha"
    assert docs[1].title == "Zeta"
