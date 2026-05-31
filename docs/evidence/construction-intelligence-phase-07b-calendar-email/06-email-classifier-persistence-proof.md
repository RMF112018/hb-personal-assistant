# Phase 07B Prompt 06 — Email Classifier Persistence: Live Real-Store Proof (redacted)

Date: 2026-05-31 · Branch: `main` · Repo SHA at start: `9fb1c2a` · Package `1.3.0` · Schema head V23
· Classification version `phase06-email-ollama-v1`

This is a redacted live proof that the new V14 `ConstructionStore` helpers persist correctly
against the **real local store** at
`~/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite`.
All values below are structural facts only — no UPN, tenant GUID, oid, scopes, file paths,
raw subjects, raw email addresses, URLs, tokens, or body content are recorded.

## Posture

- `hb-assistant auth status --json` → `token_type=delegated` (read-only delegated posture).
  The email classifier path is **Graph-free**: it reads already-indexed local data
  (`list_email_project_matches`, `get_email_message`, optional local encrypted-body vault)
  and never calls Microsoft 365. No re-auth was required for persistence; mailbox stays
  read-only.

## Live classify (apply) against the real store

Drove `EmailIntelligenceClassifier(store).classify(project_key=<redacted-pilot-key>,
lookback_days=30, dry_run=False, mock_output=<deterministic valid JSON>)`. A deterministic
mock output was used so the run does not depend on a live model; the persistence path
exercised is identical.

| Metric | Value |
| --- | --- |
| messages_considered | 40 |
| model_attempted_count | 40 |
| model_outputs_valid | true |
| model_outputs_invalid_count | 0 |
| review_required_count | 7 |
| report.persisted | true |
| report.plaintext_persisted | false |
| persisted rows (`list_email_model_classifications`) | 40 |

Sample persisted record (safe fields only): `classification_status=valid`,
`advisory_only=true`, `plaintext_body_persisted=false`, `raw_prompt_persisted=false`,
`raw_response_persisted=false`, `topic_labels=["schedule"]`, `review_required=false`.

## Guardrail verification (read-only SQL over the real table)

```
SELECT COUNT(*), SUM(advisory_only), SUM(plaintext_body_persisted),
       SUM(raw_prompt_persisted), SUM(raw_response_persisted), SUM(review_required)
FROM email_model_classifications;
→ total=40  advisory_only=40  plaintext_body_persisted=0
  raw_prompt_persisted=0  raw_response_persisted=0  review_required=7
```

- Forbidden raw-content columns (`body`, `body_text`, `body_html`, `raw_email`,
  `plain_text`, `raw_prompt`, `raw_response`, `prompt`, `response`): **NONE present**.
  (The `*_persisted` columns are advisory guard flags, not content.)
- Leak scan over persisted JSON columns for `@` (raw email), `http` (URL): **0 hits**.
- Distinct `classification_status`: `valid=40`. Distinct `topic_labels_json`: `["schedule"]`.

## Idempotency

Re-running the same live apply left the row count unchanged at **40** (upsert keyed on
`(message_id, model_name, schema_version)`).

## Gate & no-writeback proof after the live write

- `data-quality gates --json` → gate `email_classifier_persistence_status` moved from
  `deferred_not_blocking` (observed=false) **before** the write to `pass` (observed=true,
  blocking=0) **after**.
- `data-quality no-writeback-proof --json` → `proof_passed=true`,
  `no_raw_values_persisted=true` (still passing after the live local write).

## Scope notes

- No Microsoft 365 mutation/writeback occurred; no Phase 07D meeting-prep readiness is claimed.
- The no-writeback prover does not yet scan the V14/V23 tables — deferred to Phase 07B Prompt 12.
