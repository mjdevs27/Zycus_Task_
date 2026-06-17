# Design Note

This note covers the production concerns behind the ticket-triage agent (Task 1)
and the TAM account-health summariser (Task 2): how each fails, how those
failures are detected and mitigated, the latency/quality trade-off, data
sensitivity, and scaling to 10x ticket volume. Every claim maps to something
actually implemented in this repository.

## 1. Failure Modes

### Failure mode 1: Incorrect KB retrieval

Triage retrieves knowledge-base context with TF-IDF (`app/retrieval.py`) over the
Markdown docs loaded by `app/kb_loader.py`. The risk is retrieving an
irrelevant doc and either drafting a misleading first response or asserting a
false "known issue" match.

- **Detection.** Retrieval scores are returned on every `RetrievedDocument`, so
  low-relevance matches are visible in the API response and the eval report. The
  eval scorer (`evals/scoring.py`) includes a known-issue safety check that
  fails any case where `known_issue_match.doc_path` is not among the retrieved
  doc paths — i.e. a hallucinated citation.
- **Mitigation.** A known-issue match is only allowed when it cites a real
  retrieved doc; the `KnownIssueMatch` schema requires `doc_title`, `doc_path`,
  and `match_reason` whenever `matched=True`. When the KB is missing, retrieval
  returns nothing and triage says so honestly rather than inventing a citation.

### Failure mode 2: Invalid or hallucinated LLM output

The model may return malformed JSON, miss required fields, or invent content.

- **Detection.** All model output is parsed and validated through Pydantic
  schemas (`app/schemas.py`): `TicketTriageResponse`, `AccountBriefResponse`,
  and their nested models reject empty required fields and out-of-range values.
  The LLM client (`app/llm_client.py`) robustly extracts JSON (fence stripping,
  balanced-object extraction) and raises typed errors on failure.
- **Mitigation.** On any validation or client error, both agents fall back to a
  deterministic, schema-valid local response instead of surfacing a broken
  result. The fallback is explicit (`deterministic=True`), never disguised as a
  model answer. Account-brief evidence quotes are verified against actual ticket
  text and dropped if they do not match, so the model cannot fabricate a quote.

### Failure mode 3: Missed churn/escalation signal

The summariser must not miss a customer threatening to cancel or demanding
escalation.

- **Detection.** `app/account_summarizer.py` runs a local risk-signal pass
  (`detect_risk_quote_candidates`) over recent ticket text for churn,
  escalation, and unresolved-issue terms, independent of the LLM. Eval cases
  include adversarial inputs to exercise this path.
- **Mitigation.** Detected exact quotes are passed to the prompt as preferred,
  verbatim evidence, and every emitted `RiskFlag` must carry an
  `evidence_quote` that exists in real ticket text. Unverifiable flags are
  removed (`sanitize_risk_flags`), trading recall for trustworthiness: a flag
  that survives is always backed by a real quote.

## 2. Latency vs Quality

The system defaults to `temperature=0` and a fixed `seed` (`app/config.py`,
`app/llm_client.py`) for deterministic, reviewable output — important for an
internal tool whose outputs feed customer responses and for a reproducible eval
harness. TF-IDF retrieval is local and fast, adding negligible latency versus an
embedding service while keeping the dependency surface small. Streaming for the
account brief (`app/streaming.py`) is deterministic section-by-section NDJSON,
which improves *perceived* latency (sections appear progressively) without
sacrificing reproducibility or depending on provider token streaming. When the
LLM is slow or unavailable, the deterministic fallback returns immediately, so a
TAM is never blocked. The deliberate trade-off is breadth-of-phrasing for
consistency: we prefer stable, verifiable answers over more fluent but
non-reproducible ones.

## 3. Data Sensitivity

Support tickets and account records contain PII. Before any account or ticket
text is sent to the LLM, it is redacted by `app/pii.py`, and the summariser
operates on redacted copies throughout the LLM path — evidence-quote
verification runs against the same redacted text, so quotes stay both verifiable
and PII-free. Secrets are handled separately: the API key lives only in a
gitignored `.env`; `.env.example` holds placeholders only; and
`scripts/check_secrets.py` (also run in CI) detects likely leaked keys and fails
if `.env` is tracked. The LLM client never logs raw prompts or unredacted
content. This project does **not** claim SOC2 compliance, encryption at rest,
private deployment, or enterprise observability — none of those are implemented,
and the note avoids overstating guarantees.

## 4. Scaling to 10x Ticket Volume

At 10x volume the bottlenecks are LLM calls and per-account ticket scans, not the
lightweight local components. The design already supports horizontal scaling:
the FastAPI app is stateless, data loading is isolated behind
`app/data_loader.py`, and agents are constructed per request, so multiple
workers scale linearly. Account briefs only consider the last 90 days of
tickets with deterministic sorting, bounding per-request work regardless of total
history. To go further: cache TF-IDF vectorization of the KB (it is rebuilt
per process today), batch or queue triage for non-interactive backlogs, and add
a persistent store/index if the dataset outgrows in-memory JSON loading. The eval
harness and CI (`.github/workflows/evals.yml`) provide a regression gate so
quality can be re-measured as prompts, retrieval, or scale change — the harness
runs on every commit and works even without the official dataset.
