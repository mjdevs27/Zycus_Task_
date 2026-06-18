# Graph Report - us-delivery-ai-support  (2026-06-19)

## Corpus Check
- 47 files · ~20,104 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 704 nodes · 1924 edges · 27 communities (19 shown, 8 thin omitted)
- Extraction: 80% EXTRACTED · 20% INFERRED · 0% AMBIGUOUS · INFERRED: 377 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]

## God Nodes (most connected - your core abstractions)
1. `Settings` - 67 edges
2. `TicketTriageAgent` - 56 edges
3. `TicketTriageRequest` - 46 edges
4. `AccountBriefResponse` - 41 edges
5. `AccountHealthSummarizer` - 37 edges
6. `LLMClient` - 37 edges
7. `TicketTriageResponse` - 35 edges
8. `KnowledgeBaseRetriever` - 30 edges
9. `redact_pii()` - 29 edges
10. `KnownIssueMatch` - 29 edges

## Surprising Connections (you probably didn't know these)
- `EvalCaseResult` --uses--> `EvalCaseResult`  [INFERRED]
  evals/scoring.py → app/schemas.py
- `AccountBriefResponse` --uses--> `AccountNotFoundError`  [INFERRED]
  tests/test_api.py → app/account_summarizer.py
- `TicketTriageResponse` --uses--> `AccountNotFoundError`  [INFERRED]
  tests/test_api.py → app/account_summarizer.py
- `test_account_not_found()` --calls--> `AccountNotFoundError`  [EXTRACTED]
  tests/test_api.py → app/account_summarizer.py
- `AccountHealthSummarizer` --uses--> `AccountHealthSummarizer`  [INFERRED]
  evals/run_evals.py → app/account_summarizer.py

## Import Cycles
- 1-file cycle: `app/account_summarizer.py -> app/account_summarizer.py`
- 1-file cycle: `app/data_loader.py -> app/data_loader.py`

## Communities (27 total, 8 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (68): EvidenceQuoteError, AccountBriefResponse, LLMClient, Settings, Raised when a required risk evidence quote cannot be verified., get_settings(), Application configuration for the US Delivery AI Support assignment., Runtime settings loaded from environment variables or .env. (+60 more)

### Community 1 - "Community 1"
Cohesion: 0.17
Nodes (33): AccountDataError, AccountNotFoundError, AccountSummaryError, Base exception for account summarisation problems., Raised when no account matches the requested ID., Raised for invalid input or unusable account data., DatasetError, EmptyDatasetError (+25 more)

### Community 2 - "Community 2"
Cohesion: 0.11
Nodes (41): discover_markdown_files(), EmptyKnowledgeBaseError, extract_title(), infer_category(), load_kb_document(), load_knowledge_base(), make_doc_id(), MissingKnowledgeBaseError (+33 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (44): Any, Local, deterministic PII redaction and data-safety utilities.  This module provi, Redact the query string of any URL, keeping the domain/path intact., Apply all redactors in a stable, deterministic order.      Returns an empty stri, Recursively redact strings inside dicts/lists; leave other types as-is., Return a new dict with all string values redacted. Input is not mutated., Return a new dict with all string values redacted. Input is not mutated., Replace email addresses with ``[REDACTED_EMAIL]``. (+36 more)

### Community 4 - "Community 4"
Cohesion: 0.12
Nodes (28): Structured output for Task 1., Input for Task 1 ticket triage.      The assessment allows either free text or J, Return a normalized ticket string for retrieval and prompting., TicketTriageRequest, TicketTriageResponse, Coerce and sanitize raw LLM output into a valid response dict., Triage one support ticket into a structured, validated decision., TicketTriageAgent (+20 more)

### Community 5 - "Community 5"
Cohesion: 0.07
Nodes (42): _document_text(), KnowledgeBaseRetriever, make_snippet(), normalize_text(), KBDocument, RetrievedDocument, Deterministic TF-IDF retrieval over Markdown knowledge-base documents.  The asse, Return the top-k most relevant documents for *query*.          Returns an empty (+34 more)

### Community 6 - "Community 6"
Cohesion: 0.09
Nodes (51): AccountHealthSummarizer, EvalCaseResult, EvalReport, Scored result for one eval case., Evaluation summary report., escape_markdown_table_cell(), model_to_dict(), EvalReport (+43 more)

### Community 7 - "Community 7"
Cohesion: 0.13
Nodes (23): get_prompt_version(), load_prompt(), parse_prompt_metadata(), _prompt_dir(), PromptRenderError, Path, Settings, Prompt versioning: load external Markdown prompts and render them safely.  Promp (+15 more)

### Community 8 - "Community 8"
Cohesion: 0.05
Nodes (64): _build_fallback_summary(), _coerce_risk_flag(), _default_talking_points(), detect_risk_quote_candidates(), _extract_quote_for_term(), extract_ticket_text(), filter_tickets_last_90_days(), find_account_by_id() (+56 more)

### Community 12 - "Community 12"
Cohesion: 0.18
Nodes (6): account_cases(), _load(), Path, Validation tests for the Task 3 evaluation case files.  These tests check the st, test_files_are_valid_json(), triage_cases()

### Community 13 - "Community 13"
Cohesion: 0.07
Nodes (36): AccountBriefResponse, Risk or escalation flag for Task 2., Structured output for Task 2 TAM account health summarisation., RiskFlag, json_line(), model_to_dict(), AccountBriefResponse, Any (+28 more)

### Community 14 - "Community 14"
Cohesion: 0.10
Nodes (40): clamp_score(), count_sentences(), extract_all_text_from_obj(), has_non_empty_field(), EvalCaseResult, quote_exists_in_tickets(), Deterministic, rule-based scoring engine for Task 3 evaluation.  Each case is sc, Clamp *score* into [0, 1] and round to 3 decimals. (+32 more)

### Community 15 - "Community 15"
Cohesion: 0.24
Nodes (14): main(), _provider_label(), Streamlit thin UI for the US Delivery AI Support tools (bonus).  A lightweight d, Convert a Pydantic v2/v1 model or plain dict into a dict., Describe the configured provider without revealing any secret., Render the sidebar and return the selected section name., render_about(), render_account_brief() (+6 more)

### Community 17 - "Community 17"
Cohesion: 0.21
Nodes (27): add_fail(), add_pass(), add_warn(), check_bonus_files(), check_dataset(), check_docs(), check_eval_report(), check_required_files() (+19 more)

### Community 18 - "Community 18"
Cohesion: 0.12
Nodes (27): check_dataset_status(), filter_tickets_for_account(), load_json_file(), normalize_records(), DatasetStatus, Load a required official JSON dataset file.      Args:         path: File path., Normalize supported dataset shapes into a list of dictionaries.      Supported s, Return tickets linked to the given account ID using flexible account fields. (+19 more)

### Community 19 - "Community 19"
Cohesion: 0.19
Nodes (13): filter_last_n_days_tickets(), _path_exists(), _path_non_empty(), datetime, Path, Official dataset loading utilities with missing-data safety., Filter tickets to the last *days* days using flexible date fields.      Tickets, Check whether *path* exists and is a regular file. (+5 more)

### Community 20 - "Community 20"
Cohesion: 0.20
Nodes (9): AccountHealthSummarizer, Generate a deterministic TAM account health brief for one account., account_brief(), raise_api_error(), Generate a TAM account health brief for *account_id*., Run the evaluation harness and return a summary plus report paths., Raise an ``HTTPException`` with a consistent structured detail payload., run_evals_endpoint() (+1 more)

### Community 21 - "Community 21"
Cohesion: 0.27
Nodes (8): load_account_by_id(), load_accounts(), load_tickets(), Any, Settings, Load official support tickets., Load official customer account summaries., Find an account by a flexible ID field.      Supports fields: account_id, id, cu

## Knowledge Gaps
- **2 isolated node(s):** `Any`, `Path`
  These have ≤1 connection - possible missing edges or undocumented components.
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Settings` connect `Community 0` to `Community 1`, `Community 2`, `Community 4`, `Community 7`, `Community 8`, `Community 18`, `Community 19`, `Community 20`, `Community 21`?**
  _High betweenness centrality (0.130) - this node is a cross-community bridge._
- **Why does `TicketTriageAgent` connect `Community 4` to `Community 0`, `Community 1`, `Community 5`, `Community 6`, `Community 7`, `Community 15`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **Why does `run_all_evals()` connect `Community 6` to `Community 1`, `Community 4`, `Community 15`, `Community 17`, `Community 18`, `Community 20`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Are the 48 inferred relationships involving `Settings` (e.g. with `AccountDataError` and `AccountHealthSummarizer`) actually correct?**
  _`Settings` has 48 INFERRED edges - model-reasoned connections that need verification._
- **Are the 24 inferred relationships involving `TicketTriageAgent` (e.g. with `AccountHealthSummarizer` and `AccountBriefResponse`) actually correct?**
  _`TicketTriageAgent` has 24 INFERRED edges - model-reasoned connections that need verification._
- **Are the 22 inferred relationships involving `TicketTriageRequest` (e.g. with `AccountHealthSummarizer` and `AccountBriefResponse`) actually correct?**
  _`TicketTriageRequest` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Are the 24 inferred relationships involving `AccountBriefResponse` (e.g. with `AccountDataError` and `AccountHealthSummarizer`) actually correct?**
  _`AccountBriefResponse` has 24 INFERRED edges - model-reasoned connections that need verification._