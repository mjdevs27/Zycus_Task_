"""Task 1 — Intelligent ticket triage agent.

The agent ingests a support ticket (free text or subject/body), redacts PII
locally, retrieves relevant knowledge-base context, and asks the LLM for a
structured triage decision. It guards against hallucinated KB matches and
degrades gracefully to a deterministic local fallback when no LLM is available.
"""

from __future__ import annotations

import logging

from pydantic import ValidationError

from app.config import Settings, get_settings
from app.kb_loader import KnowledgeBaseError, load_knowledge_base
from app.llm_client import LLMClient, LLMClientError
from app.pii import redact_pii
from app.prompt_loader import PromptError, get_prompt_version, load_prompt, render_prompt
from app.retrieval import KnowledgeBaseRetriever
from app.schemas import (
    KnownIssueMatch,
    RetrievedDocument,
    TicketTriageRequest,
    TicketTriageResponse,
)

logger = logging.getLogger("app.triage_agent")

_VALID_TIERS = {"P1", "P2", "P3", "P4"}
_NO_KB_REASON = "No knowledge-base documents were available for retrieval."
_BAD_PATH_REASON = (
    "The referenced knowledge-base document was not among the retrieved "
    "documents and was rejected to prevent a hallucinated match."
)


class TriageError(Exception):
    """Raised for invalid triage input that cannot be processed."""


class TicketTriageAgent:
    """Triage one support ticket into a structured, validated decision."""

    def __init__(
        self,
        retriever: KnowledgeBaseRetriever | None = None,
        llm_client: LLMClient | None = None,
        prompt_name: str = "triage_v1",
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.prompt_name = prompt_name
        self.retriever = retriever if retriever is not None else self._build_retriever()
        self.llm_client = llm_client if llm_client is not None else LLMClient(
            settings=self.settings
        )
        self.prompt_version = self._resolve_prompt_version()

    # -- setup helpers -------------------------------------------------------

    def _build_retriever(self) -> KnowledgeBaseRetriever | None:
        """Build a retriever from KB docs, or None if KB is unavailable."""
        try:
            docs = load_knowledge_base(settings=self.settings)
        except KnowledgeBaseError:
            logger.info("Knowledge base unavailable; triage will run without KB.")
            return None
        return KnowledgeBaseRetriever(docs, top_k=self.settings.top_k_kb_docs)

    def _resolve_prompt_version(self) -> str:
        try:
            return get_prompt_version(self.prompt_name, settings=self.settings)
        except PromptError:
            return self.prompt_name

    # -- core flow -----------------------------------------------------------

    def triage(self, request: TicketTriageRequest) -> TicketTriageResponse:
        """Run the full triage pipeline and return a validated response."""
        ticket_text = self._build_ticket_text(request)
        redacted_text = redact_pii(ticket_text)
        docs = self._retrieve(redacted_text)

        try:
            prompt = self._build_prompt(redacted_text, docs)
            raw = self.llm_client.complete_json(
                prompt,
                system_message=(
                    "You are a deterministic support triage assistant. "
                    "Return JSON only."
                ),
            )
        except (LLMClientError, PromptError) as exc:
            # No LLM key, transport failure, or an unavailable/invalid prompt
            # template must all degrade to the deterministic local fallback
            # rather than crash the request.
            return self._fallback_response(redacted_text, docs, exc)

        try:
            processed = self._post_process_response(raw, docs, redacted_text)
            return TicketTriageResponse(**processed)
        except (ValidationError, ValueError, KeyError, TypeError) as exc:
            logger.info("LLM output failed validation; using fallback: %s", exc)
            return self._fallback_response(redacted_text, docs, exc)

    # -- helpers -------------------------------------------------------------

    def _build_ticket_text(self, request: TicketTriageRequest) -> str:
        text = (request.combined_text or "").strip()
        if not text:
            raise TriageError("Ticket has no usable text for triage.")
        return text

    def _retrieve(self, query: str) -> list[RetrievedDocument]:
        if self.retriever is None or not self.retriever.is_ready():
            return []
        return self.retriever.retrieve(query)

    @staticmethod
    def _format_retrieved_docs(docs: list[RetrievedDocument]) -> str:
        if not docs:
            return "No knowledge-base documents were retrieved."
        blocks = []
        for index, doc in enumerate(docs, start=1):
            blocks.append(
                f"[DOC {index}]\n"
                f"Title: {doc.title}\n"
                f"Path: {doc.path}\n"
                f"Score: {doc.score:.4f}\n"
                f"Snippet: {doc.snippet}"
            )
        return "\n\n".join(blocks)

    def _build_prompt(self, ticket_text: str, docs: list[RetrievedDocument]) -> str:
        template = load_prompt(self.prompt_name, settings=self.settings)
        return render_prompt(
            template,
            {
                "ticket_text": ticket_text,
                "retrieved_kb_docs": self._format_retrieved_docs(docs),
                "prompt_version": self.prompt_version,
            },
        )

    def _post_process_response(
        self,
        raw: dict,
        docs: list[RetrievedDocument],
        ticket_text: str,
    ) -> dict:
        """Coerce and sanitize raw LLM output into a valid response dict."""
        result: dict = dict(raw or {})

        result["product_area"] = (result.get("product_area") or "unknown").strip() or "unknown"
        result["issue_category"] = (
            result.get("issue_category") or "unknown"
        ).strip() or "unknown"
        result["reasoning"] = (
            result.get("reasoning") or "No reasoning provided by the model."
        ).strip()
        result["recommended_team"] = (
            result.get("recommended_team") or "Customer Success"
        ).strip() or "Customer Success"
        result["draft_first_response"] = (
            result.get("draft_first_response")
            or "Thank you for reaching out. We are reviewing your issue and will "
            "follow up with next steps shortly."
        ).strip()

        # Urgency tier normalization.
        result["urgency_tier"] = self._normalize_tier(
            result.get("urgency_tier"), ticket_text
        )

        # Known-issue hallucination guard.
        result["known_issue_match"] = self._sanitize_known_issue(
            result.get("known_issue_match"), docs
        )

        result["prompt_version"] = self.prompt_version
        result["retrieved_docs"] = [doc.model_dump() for doc in docs]
        result["deterministic"] = True
        return result

    def _normalize_tier(self, tier, ticket_text: str) -> str:
        if isinstance(tier, str):
            candidate = tier.strip().upper()
            if candidate in _VALID_TIERS:
                return candidate
        # Unknown/invalid tier: fall back to deterministic keyword inference.
        return self._infer_urgency(ticket_text)

    def _sanitize_known_issue(self, raw_match, docs: list[RetrievedDocument]) -> dict:
        no_match = {
            "matched": False,
            "doc_title": None,
            "doc_path": None,
            "match_reason": _NO_KB_REASON if not docs else _BAD_PATH_REASON,
            "confidence": 0.0,
        }
        # No docs retrieved -> never allow a match.
        if not docs:
            return {**no_match, "match_reason": _NO_KB_REASON}

        if not isinstance(raw_match, dict) or not raw_match.get("matched"):
            return {
                "matched": False,
                "doc_title": None,
                "doc_path": None,
                "match_reason": None,
                "confidence": 0.0,
            }

        path = raw_match.get("doc_path")
        retrieved_by_path = {doc.path: doc for doc in docs}
        if path not in retrieved_by_path:
            # Hallucinated / non-retrieved path -> reject the match.
            return {**no_match, "match_reason": _BAD_PATH_REASON}

        doc = retrieved_by_path[path]
        confidence = raw_match.get("confidence")
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = round(doc.score, 4)
        confidence = max(0.0, min(1.0, confidence))
        return {
            "matched": True,
            "doc_title": doc.title,
            "doc_path": doc.path,
            "match_reason": (
                raw_match.get("match_reason")
                or "The ticket aligns with this retrieved knowledge-base document."
            ),
            "confidence": confidence,
        }

    # -- fallback ------------------------------------------------------------

    def _fallback_response(
        self,
        ticket_text: str,
        docs: list[RetrievedDocument],
        error: Exception,
    ) -> TicketTriageResponse:
        """Deterministic, rule-based triage used when the LLM is unavailable."""
        tier = self._infer_urgency(ticket_text)
        product_area, team = self._infer_area_and_team(ticket_text)
        known_issue = self._fallback_known_issue(docs)

        reasoning = (
            "Local fallback triage (no LLM was available). Urgency was assigned "
            f"by keyword rules: {tier}. Reason for fallback: "
            f"{type(error).__name__}."
        )
        return TicketTriageResponse(
            product_area=product_area,
            issue_category="unknown",
            urgency_tier=tier,
            reasoning=reasoning,
            known_issue_match=KnownIssueMatch(**known_issue),
            recommended_team=team,
            draft_first_response=(
                "Thank you for contacting support. We have received your ticket "
                "and a specialist will review it. This acknowledgement was "
                "generated by local fallback triage."
            ),
            retrieved_docs=docs,
            prompt_version=self.prompt_version,
            deterministic=True,
        )

    @staticmethod
    def _infer_urgency(text: str) -> str:
        lowered = (text or "").lower()
        p1 = ("outage", "all users", "production down", "production-blocking",
              "data loss", "security", "breach", "down for everyone")
        p2 = ("broken", "blocked", "urgent", "cannot", "can't", "major",
              "not working", "failing")
        p4 = ("how to", "how-to", "documentation", "question", "doc ", "minor",
              "clarification")
        if any(term in lowered for term in p1):
            return "P1"
        if any(term in lowered for term in p2):
            return "P2"
        if any(term in lowered for term in p4):
            return "P4"
        return "P3"

    @staticmethod
    def _infer_area_and_team(text: str) -> tuple[str, str]:
        lowered = (text or "").lower()
        if any(t in lowered for t in ("sso", "saml", "login", "auth", "mfa")):
            return "Authentication/SSO", "Authentication/SSO"
        if any(t in lowered for t in ("invoice", "billing", "payment", "charge")):
            return "Billing", "Billing"
        if any(t in lowered for t in ("dashboard", "report", "analytics")):
            return "Analytics", "Data Platform"
        return "unknown", "Customer Success"

    @staticmethod
    def _fallback_known_issue(docs: list[RetrievedDocument]) -> dict:
        if docs and docs[0].score > 0:
            top = docs[0]
            return {
                "matched": True,
                "doc_title": top.title,
                "doc_path": top.path,
                "match_reason": (
                    "Local fallback matched the top retrieved KB document by "
                    "TF-IDF similarity."
                ),
                "confidence": max(0.0, min(1.0, round(top.score, 4))),
            }
        return {
            "matched": False,
            "doc_title": None,
            "doc_path": None,
            "match_reason": _NO_KB_REASON if not docs else None,
            "confidence": 0.0,
        }
