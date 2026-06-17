# Evaluation Report

Generated at: 2026-06-19T03:06:49.603061+00:00
Dataset ready: false

## Summary

| Metric | Value |
|---|---:|
| Total cases | 10 |
| Passed | 5 |
| Failed | 5 |
| Average score | 0.5 |

## Results

| ID | Task | Name | Passed | Score | Adversarial | Notes |
|---|---|---|---:|---:|---:|---|
| triage_001 | triage | SSO login outage should receive high urgency | true | 1.0 | false |  |
| triage_002 | triage | Billing invoice issue should be triaged with a clear area | true | 1.0 | false |  |
| triage_003 | triage | Analytics dashboard performance issue | true | 1.0 | false |  |
| triage_004 | triage | Documentation/how-to question should be low urgency | true | 1.0 | false |  |
| triage_005 | triage | Adversarial ambiguous ticket must not crash | true | 1.0 | true |  |
| account_001 | account_summary | Account brief contains required three sections | false | 0.0 | false | Official dataset is not ready, so this account-summary case could not be executed without inventing account data. |
| account_002 | account_summary | Risk flags require direct ticket quotes | false | 0.0 | false | Official dataset is not ready, so this account-summary case could not be executed without inventing account data. |
| account_003 | account_summary | Determinism check for repeated runs | false | 0.0 | false | Official dataset is not ready, so this account-summary case could not be executed without inventing account data. |
| account_004 | account_summary | Account with no recent tickets still produces useful talking points | false | 0.0 | false | Official dataset is not ready, so this account-summary case could not be executed without inventing account data. |
| account_005 | account_summary | Adversarial missing or incomplete account must not hallucinate | false | 0.0 | true | Account case error: EmptyDatasetError: accounts dataset contains zero records. |
