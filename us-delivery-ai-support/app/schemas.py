"""Pydantic schemas for API contracts, AI outputs, dataset status, and eval reports."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator


UrgencyTier = Literal["P1", "P2", "P3", "P4"]
Severity = Literal["low", "medium", "high"]
EvalTask = Literal["triage", "account_summary"]


class DatasetStatus(BaseModel):
    """Readiness status for the official assignment dataset."""

    tickets_file_exists: bool
    tickets_file_non_empty: bool
    accounts_file_exists: bool
    accounts_file_non_empty: bool
    kb_dir_exists: bool
    kb_docs_count: int
    ready: bool
    message: str
    missing_or_empty: list[str] = Field(default_factory=list)


class KBDocument(BaseModel):
    """A loaded Markdown knowledge-base document."""

    doc_id: str
    title: str
    path: str
    content: str
    category: str | None = None

    @field_validator("content")
    @classmethod
    def content_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Knowledge-base document content cannot be empty")
        return value


class RetrievedDocument(BaseModel):
    """A document retrieved from the knowledge base for RAG context."""

    doc_id: str
    title: str
    path: str
    score: float = Field(ge=0)
    snippet: str


class TicketTriageRequest(BaseModel):
    """Input for Task 1 ticket triage.

    The assessment allows either free text or JSON with subject + body.
    """

    text: str | None = None
    subject: str | None = None
    body: str | None = None

    @model_validator(mode="after")
    def validate_text_or_subject_body(self) -> "TicketTriageRequest":
        has_text = bool((self.text or "").strip())
        has_subject = bool((self.subject or "").strip())
        has_body = bool((self.body or "").strip())
        if not has_text and not (has_subject or has_body):
            raise ValueError("Provide either text or subject/body for ticket triage")
        return self

    @computed_field
    @property
    def combined_text(self) -> str:
        """Return a normalized ticket string for retrieval and prompting."""
        if self.text and self.text.strip():
            return self.text.strip()
        parts = []
        if self.subject and self.subject.strip():
            parts.append(f"Subject: {self.subject.strip()}")
        if self.body and self.body.strip():
            parts.append(f"Body: {self.body.strip()}")
        return "\n".join(parts).strip()


class KnownIssueMatch(BaseModel):
    """Known issue match surfaced from the knowledge base."""

    matched: bool
    doc_title: str | None = None
    doc_path: str | None = None
    match_reason: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_match_fields(self) -> "KnownIssueMatch":
        if self.matched:
            if not self.doc_title or not self.doc_path or not self.match_reason:
                raise ValueError(
                    "Matched known issue requires doc_title, doc_path, and match_reason"
                )
        return self


class TicketTriageResponse(BaseModel):
    """Structured output for Task 1."""

    product_area: str
    issue_category: str
    urgency_tier: UrgencyTier
    reasoning: str
    known_issue_match: KnownIssueMatch
    recommended_team: str
    draft_first_response: str
    retrieved_docs: list[RetrievedDocument] = Field(default_factory=list)
    prompt_version: str
    deterministic: bool = True

    @field_validator(
        "product_area",
        "issue_category",
        "reasoning",
        "recommended_team",
        "draft_first_response",
        "prompt_version",
    )
    @classmethod
    def required_strings_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Required string field cannot be empty")
        return value.strip()


class RiskFlag(BaseModel):
    """Risk or escalation flag for Task 2."""

    risk_type: str
    severity: Severity
    summary: str
    evidence_quote: str
    ticket_id: str | None = None

    @field_validator("risk_type", "summary", "evidence_quote")
    @classmethod
    def risk_fields_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Risk fields cannot be empty")
        return value.strip()


class AccountBriefResponse(BaseModel):
    """Structured output for Task 2 TAM account health summarisation."""

    account_id: str
    executive_summary: str
    open_risks_and_flagged_issues: list[RiskFlag] = Field(default_factory=list)
    recommended_talking_points: list[str] = Field(default_factory=list)
    ticket_count_used: int = Field(ge=0)
    prompt_version: str
    deterministic: bool = True

    @field_validator("account_id", "executive_summary", "prompt_version")
    @classmethod
    def account_strings_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Required account brief string field cannot be empty")
        return value.strip()

    @field_validator("recommended_talking_points")
    @classmethod
    def talking_points_must_be_clean(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]

    @computed_field
    @property
    def executive_summary_sentence_count(self) -> int:
        sentences = re.split(r"(?<=[.!?])\s+", self.executive_summary.strip())
        return len([s for s in sentences if s.strip()])


class DatasetNotReadyDetail(BaseModel):
    """Structured error payload when official data is absent."""

    error: str = "Official dataset is not ready"
    missing: list[str]
    action: str = (
        "Place the official starter repo dataset files into the expected paths "
        "and retry. Do not use external data."
    )


class EvalCase(BaseModel):
    """One evaluation test case."""

    id: str
    name: str
    task: EvalTask
    input: dict[str, Any]
    acceptance_criteria: dict[str, Any] = Field(default_factory=dict)
    adversarial: bool = False

    @field_validator("id", "name")
    @classmethod
    def eval_strings_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Eval id/name cannot be empty")
        return value.strip()


class EvalCaseResult(BaseModel):
    """Scored result for one eval case."""

    id: str
    name: str
    task: EvalTask
    passed: bool
    score: float = Field(ge=0, le=1)
    notes: list[str] = Field(default_factory=list)
    adversarial: bool = False


class EvalReport(BaseModel):
    """Evaluation summary report."""

    generated_at: str
    total_cases: int = Field(ge=0)
    passed_cases: int = Field(ge=0)
    failed_cases: int = Field(ge=0)
    average_score: float = Field(ge=0, le=1)
    results: list[EvalCaseResult] = Field(default_factory=list)
    dataset_ready: bool

    @model_validator(mode="after")
    def validate_counts(self) -> "EvalReport":
        if self.passed_cases + self.failed_cases != self.total_cases:
            raise ValueError("passed_cases + failed_cases must equal total_cases")
        return self
