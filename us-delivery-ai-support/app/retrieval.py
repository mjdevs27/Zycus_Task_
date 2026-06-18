"""Deterministic TF-IDF retrieval over Markdown knowledge-base documents.

The assessment is small, local, and must run cleanly without external vector
databases or embedding services. We therefore use scikit-learn's TF-IDF
vectorizer with cosine similarity, which is fully deterministic for a given set
of documents and queries.
"""

from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.schemas import KBDocument, RetrievedDocument


# Helper functions -----------------------------------------------------------


def normalize_text(text: str | None) -> str:
    """Convert ``None`` to ``""``, collapse whitespace, and strip."""
    if not text:
        return ""
    return " ".join(text.split())


def make_snippet(content: str, query: str, max_chars: int = 300) -> str:
    """Return a short, deterministic snippet, preferably around a query term.

    The snippet is centered on the first occurrence of any query term when
    possible; otherwise it falls back to the leading characters of the content.
    """
    normalized = normalize_text(content)
    if not normalized:
        return ""

    if len(normalized) <= max_chars:
        return normalized

    lowered = normalized.lower()
    # Find the earliest occurrence of any query term (length > 2 to skip noise).
    terms = [t for t in normalize_text(query).lower().split() if len(t) > 2]
    best_index = -1
    for term in terms:
        idx = lowered.find(term)
        if idx != -1 and (best_index == -1 or idx < best_index):
            best_index = idx

    if best_index == -1:
        return normalized[:max_chars].rstrip() + "..."

    # Center the window around the matched term, clamped to content bounds.
    half = max_chars // 2
    start = max(0, best_index - half)
    end = min(len(normalized), start + max_chars)
    start = max(0, end - max_chars)

    snippet = normalized[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(normalized):
        snippet = snippet + "..."
    return snippet


def _document_text(doc: KBDocument) -> str:
    """Combine title, category, and content to improve matching."""
    parts = [doc.title or "", doc.category or "", doc.content or ""]
    return normalize_text(" ".join(parts))


# Retriever ------------------------------------------------------------------


class KnowledgeBaseRetriever:
    """Deterministic TF-IDF retriever over loaded ``KBDocument`` objects."""

    def __init__(self, documents: list[KBDocument], top_k: int = 3) -> None:
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        self.documents: list[KBDocument] = list(documents or [])
        self.top_k = top_k
        self._vectorizer: TfidfVectorizer | None = None
        self._matrix = None
        if self.documents:
            self.build_index()

    # -- state ---------------------------------------------------------------

    def is_ready(self) -> bool:
        """True only when documents exist and the TF-IDF index has been fitted."""
        return bool(self.documents) and self._matrix is not None

    def build_index(self) -> None:
        """Build the TF-IDF matrix over combined document text."""
        if not self.documents:
            self._vectorizer = None
            self._matrix = None
            return

        corpus = [_document_text(doc) for doc in self.documents]
        self._vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 2),
            max_features=5000,
        )
        self._matrix = self._vectorizer.fit_transform(corpus)

    # -- retrieval -----------------------------------------------------------

    def retrieve(
        self, query: str, top_k: int | None = None
    ) -> list[RetrievedDocument]:
        """Return the top-k most relevant documents for *query*.

        Returns an empty list if the retriever is not ready or the query is
        blank. Zero-similarity documents are filtered out.
        """
        if not self.is_ready():
            return []

        clean_query = normalize_text(query)
        if not clean_query:
            return []

        k = top_k if top_k is not None else self.top_k
        if k < 1:
            return []

        query_vec = self._vectorizer.transform([clean_query])
        scores = cosine_similarity(query_vec, self._matrix)[0]

        # Deterministic ordering: descending score, then original doc index.
        ranked = sorted(
            range(len(self.documents)),
            key=lambda i: (-float(scores[i]), i),
        )

        results: list[RetrievedDocument] = []
        for idx in ranked:
            score = float(scores[idx])
            if score <= 0:
                continue
            doc = self.documents[idx]
            results.append(
                RetrievedDocument(
                    doc_id=doc.doc_id,
                    title=doc.title,
                    path=doc.path,
                    score=round(score, 6),
                    snippet=make_snippet(doc.content, clean_query),
                )
            )
            if len(results) >= k:
                break
        return results

    def retrieve_for_ticket(
        self,
        subject: str | None,
        body: str | None,
        text: str | None,
    ) -> list[RetrievedDocument]:
        """Build a combined query from ticket fields and retrieve docs."""
        combined = " ".join(
            part for part in (subject, body, text) if part and part.strip()
        )
        return self.retrieve(combined)

    def explain_match(self, query: str, retrieved_doc: RetrievedDocument) -> str:
        """Return a short, deterministic explanation of why a doc matched."""
        return (
            "Matched because the ticket query shares terms with the retrieved "
            f"KB document '{retrieved_doc.title}' and received a TF-IDF "
            f"similarity score of {retrieved_doc.score:.2f}."
        )
