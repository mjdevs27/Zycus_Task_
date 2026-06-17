"""Tests for app.retrieval — deterministic TF-IDF KB retrieval."""

import pytest

from app.retrieval import KnowledgeBaseRetriever, make_snippet, normalize_text
from app.schemas import KBDocument


def _sample_docs() -> list[KBDocument]:
    return [
        KBDocument(
            doc_id="troubleshooting__sso",
            title="SSO Login Troubleshooting",
            path="troubleshooting/sso.md",
            content=(
                "Users hitting SAML login errors after an SSO configuration "
                "change should verify the identity provider metadata and the "
                "assertion consumer service URL."
            ),
            category="troubleshooting",
        ),
        KBDocument(
            doc_id="billing__invoice",
            title="Billing Invoice Issues",
            path="billing/invoice.md",
            content=(
                "Incorrect invoice totals are usually caused by mismatched "
                "billing cycles or unapplied credits in the billing system."
            ),
            category="billing",
        ),
        KBDocument(
            doc_id="analytics__dashboard",
            title="Analytics Dashboard Not Loading",
            path="analytics/dashboard.md",
            content=(
                "A blank analytics dashboard often indicates a stale cache or "
                "a failed data export job for the reporting pipeline."
            ),
            category="analytics",
        ),
    ]


def test_empty_retriever_is_not_ready():
    retriever = KnowledgeBaseRetriever([])
    assert retriever.is_ready() is False
    assert retriever.retrieve("login issue") == []


def test_basic_retrieval_returns_best_match():
    retriever = KnowledgeBaseRetriever(_sample_docs())
    assert retriever.is_ready() is True
    results = retriever.retrieve("SAML login error for SSO users")
    assert results
    assert results[0].doc_id == "troubleshooting__sso"
    assert results[0].score > 0
    assert results[0].snippet


def test_top_k_respected():
    retriever = KnowledgeBaseRetriever(_sample_docs(), top_k=3)
    results = retriever.retrieve("billing invoice SSO analytics", top_k=2)
    assert len(results) <= 2


def test_empty_query_returns_empty_list():
    retriever = KnowledgeBaseRetriever(_sample_docs())
    assert retriever.retrieve("") == []
    assert retriever.retrieve("    ") == []


def test_deterministic_ordering():
    retriever = KnowledgeBaseRetriever(_sample_docs())
    first = retriever.retrieve("SSO SAML login")
    second = retriever.retrieve("SSO SAML login")
    assert [d.doc_id for d in first] == [d.doc_id for d in second]


def test_zero_score_docs_filtered():
    retriever = KnowledgeBaseRetriever(_sample_docs())
    results = retriever.retrieve("completely unrelated quantum astrophysics term")
    # No KB doc shares these terms, so nothing should be returned.
    assert results == []


def test_top_k_validation():
    with pytest.raises(ValueError):
        KnowledgeBaseRetriever(_sample_docs(), top_k=0)


def test_retrieve_for_ticket_combines_fields():
    retriever = KnowledgeBaseRetriever(_sample_docs())
    results = retriever.retrieve_for_ticket(
        subject="SSO broken", body="SAML login error", text=None
    )
    assert results
    assert results[0].doc_id == "troubleshooting__sso"


def test_explain_match_is_deterministic():
    retriever = KnowledgeBaseRetriever(_sample_docs())
    results = retriever.retrieve("SSO SAML login")
    explanation = retriever.explain_match("SSO SAML login", results[0])
    assert "TF-IDF similarity score" in explanation


def test_make_snippet_centers_on_query_term():
    content = ("alpha " * 60) + "needle " + ("omega " * 60)
    snippet = make_snippet(content, "needle", max_chars=100)
    assert "needle" in snippet
    assert len(snippet) <= 110  # max_chars plus ellipsis


def test_make_snippet_handles_empty_content():
    assert make_snippet("", "query") == ""


def test_normalize_text_handles_none():
    assert normalize_text(None) == ""
    assert normalize_text("  a   b  ") == "a b"
