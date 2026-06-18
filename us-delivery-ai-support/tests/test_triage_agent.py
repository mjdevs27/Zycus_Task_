"""Tests for app.triage_agent — Task 1 ticket triage.

All tests use fake retriever/LLM clients; no real OpenAI calls are made.
"""

from app.llm_client import MissingLLMConfigurationError
from app.schemas import RetrievedDocument, TicketTriageRequest, TicketTriageResponse
from app.triage_agent import TicketTriageAgent


# -- Fakes -------------------------------------------------------------------


class FakeRetriever:
    def __init__(self, docs):
        self._docs = docs

    def is_ready(self):
        return True

    def retrieve(self, query, top_k=None):
        return list(self._docs)


class FakeLLMClient:
    def __init__(self, response=None, raises=None):
        self._response = response
        self._raises = raises
        self.last_prompt = None
        self.last_system_message = None

    def complete_json(self, prompt, system_message=None):
        self.last_prompt = prompt
        self.last_system_message = system_message
        if self._raises is not None:
            raise self._raises
        return dict(self._response)


def _doc(path="troubleshooting/sso.md"):
    return RetrievedDocument(
        doc_id="troubleshooting__sso",
        title="SSO Login Troubleshooting",
        path=path,
        score=0.42,
        snippet="SAML login errors after SSO configuration change.",
    )


def _valid_llm_response(doc_path="troubleshooting/sso.md", matched=True):
    return {
        "product_area": "Authentication/SSO",
        "issue_category": "login_failure",
        "urgency_tier": "P2",
        "reasoning": "Users cannot log in via SSO.",
        "known_issue_match": {
            "matched": matched,
            "doc_title": "SSO Login Troubleshooting",
            "doc_path": doc_path,
            "match_reason": "Ticket matches the SSO troubleshooting doc.",
            "confidence": 0.8,
        },
        "recommended_team": "Authentication/SSO",
        "draft_first_response": "Thanks for reaching out, we are investigating.",
        "prompt_version": "triage_v1",
    }


# -- Tests -------------------------------------------------------------------


def test_basic_triage_with_subject_body():
    agent = TicketTriageAgent(
        retriever=FakeRetriever([_doc()]),
        llm_client=FakeLLMClient(_valid_llm_response()),
    )
    response = agent.triage(
        TicketTriageRequest(subject="SSO login broken", body="Users get SAML errors.")
    )
    assert isinstance(response, TicketTriageResponse)
    assert response.urgency_tier in {"P1", "P2", "P3", "P4"}
    assert response.retrieved_docs
    assert response.prompt_version == "triage_v1"
    assert response.known_issue_match.matched is True
    assert response.known_issue_match.doc_path == "troubleshooting/sso.md"


def test_free_text_input_works():
    agent = TicketTriageAgent(
        retriever=FakeRetriever([]),
        llm_client=FakeLLMClient(_valid_llm_response(matched=False)),
    )
    response = agent.triage(TicketTriageRequest(text="Billing invoice is incorrect"))
    assert isinstance(response, TicketTriageResponse)
    assert response.urgency_tier in {"P1", "P2", "P3", "P4"}


def test_pii_redacted_before_prompt():
    fake_llm = FakeLLMClient(_valid_llm_response(matched=False))
    agent = TicketTriageAgent(retriever=FakeRetriever([]), llm_client=fake_llm)
    agent.triage(
        TicketTriageRequest(
            subject="Login issue",
            body="Contact john@example.com or 9876543210 urgently",
        )
    )
    assert "[REDACTED_EMAIL]" in fake_llm.last_prompt
    assert "[REDACTED_PHONE]" in fake_llm.last_prompt
    assert "john@example.com" not in fake_llm.last_prompt
    assert "9876543210" not in fake_llm.last_prompt


def test_no_kb_docs_prevents_hallucinated_known_issue():
    fake_llm = FakeLLMClient(_valid_llm_response(doc_path="fake.md", matched=True))
    agent = TicketTriageAgent(retriever=FakeRetriever([]), llm_client=fake_llm)
    response = agent.triage(TicketTriageRequest(text="Some odd issue"))
    assert response.known_issue_match.matched is False
    assert response.known_issue_match.doc_path is None
    assert "no knowledge-base" in response.known_issue_match.match_reason.lower()


def test_hallucinated_doc_path_rejected():
    fake_llm = FakeLLMClient(
        _valid_llm_response(doc_path="knowledge-base/fake.md", matched=True)
    )
    agent = TicketTriageAgent(
        retriever=FakeRetriever([_doc(path="knowledge-base/sso.md")]),
        llm_client=fake_llm,
    )
    response = agent.triage(TicketTriageRequest(text="SSO login broken"))
    assert response.known_issue_match.matched is False
    assert response.known_issue_match.doc_path != "knowledge-base/fake.md"


def test_fallback_without_llm():
    fake_llm = FakeLLMClient(raises=MissingLLMConfigurationError("no key"))
    agent = TicketTriageAgent(retriever=FakeRetriever([]), llm_client=fake_llm)
    response = agent.triage(
        TicketTriageRequest(text="Production outage, all users cannot login.")
    )
    assert isinstance(response, TicketTriageResponse)
    assert response.urgency_tier == "P1"
    assert "fallback" in response.reasoning.lower()


def test_invalid_urgency_from_llm_handled():
    bad = _valid_llm_response(matched=False)
    bad["urgency_tier"] = "Critical"
    agent = TicketTriageAgent(
        retriever=FakeRetriever([]), llm_client=FakeLLMClient(bad)
    )
    response = agent.triage(
        TicketTriageRequest(text="Security breach causing data loss for all users")
    )
    assert response.urgency_tier in {"P1", "P2", "P3", "P4"}


def test_valid_match_is_preserved():
    agent = TicketTriageAgent(
        retriever=FakeRetriever([_doc()]),
        llm_client=FakeLLMClient(_valid_llm_response()),
    )
    response = agent.triage(TicketTriageRequest(text="SSO SAML login error"))
    assert response.known_issue_match.matched is True
    assert response.known_issue_match.confidence is not None
