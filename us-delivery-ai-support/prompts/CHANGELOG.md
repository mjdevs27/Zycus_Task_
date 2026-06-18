# Prompt Changelog

## triage_v1
- Initial prompt for Task 1 ticket triage.
- Adds structured JSON contract.
- Adds urgency rubric P1-P4.
- Adds known issue matching rules (no fabricated doc paths).
- Adds first-response drafting rules.

## account_summary_v1
- Initial prompt for Task 2 TAM account brief.
- Adds deterministic output requirement.
- Adds mandatory direct-quote rule for churn/escalation flags.
- Adds severity-based risk sorting.
- Adds `{{risk_quote_candidates}}` section so locally-detected exact quotes are
  preferred verbatim as evidence (keeps quotes verifiable, prevents invention).

## judge_v1
- Initial optional LLM-as-judge prompt for the eval harness.
- Scores 0-1 against provided acceptance criteria only.
