# 23 — Phase 07B: Email Classifier Persistence (V14 store helpers)

Phase 07B Prompt 06. Status: implemented at this record's commit.

## Problem

The V14 advisory read model (`email_model_classifications`, schema head V23) and the
`EmailIntelligenceClassifier` runtime already existed, but the `ConstructionStore` never
gained the persistence helpers the classifier and its tests depend on. The classifier's
`_persist()` path (`construction/email/email_classifier.py`) calls
`upsert_email_model_classification(...)`, which did not exist — so any non-dry-run classify
would raise `AttributeError`. Eight tests were parked as `xfail(strict=False)` waiting on it
(7 in `tests/test_email_classifier.py`, 1 in `tests/test_email_model_classifications_schema_v14.py`).

## Change

Three additive read/write helpers on `ConstructionStore`
(`construction/store/repositories.py`), mirroring the existing email/calendar patterns
(`upsert_email_project_match`, `upsert_calendar_project_match_candidate`,
`_email_message_row_to_record`):

- **`upsert_email_model_classification(*, ...)`** — `INSERT ... ON CONFLICT(message_id,
  model_name, schema_version) DO UPDATE`, inside `with transaction(conn)`. List/dict args
  are encoded via the existing `_dump_json` staticmethod into the `*_json` columns;
  `review_required` is stored 0/1; `updated_utc` refreshed on update. Idempotent by the
  V14 unique key.
- **`get_email_model_classification(*, message_id, model_name, schema_version)`** — returns
  the row as a dict with `*_json` columns decoded back to lists/dicts and the
  advisory/guard flags returned as `bool`; `None` if absent.
- **`list_email_model_classifications(*, project_key=None, message_id=None,
  review_required=None, limit=1000)`** — filtered list, newest first, same decoding.

The 8 `xfail` markers were removed (test bodies unchanged — they already encode the
intended behavior).

## Guardrail invariants (preserved by design, not just by tests)

- The advisory/guard CHECK columns (`advisory_only=1`, `plaintext_body_persisted=0`,
  `raw_prompt_persisted=0`, `raw_response_persisted=0`) are **never written** by the upsert —
  schema defaults hold them, so model output stays advisory-only and no raw body, prompt, or
  response can be persisted.
- No raw email body, prompt, or model response is accepted as a parameter; only
  labels/flags/hashes round-trip through the `*_json` columns.
- Local SQLite writes occur only on the non-dry-run (`dry_run=False`) classify path; dry-run
  remains the default and persists nothing.
- The classifier path is **Graph-free** — it reads already-indexed local data
  (`list_email_project_matches`, `get_email_message`, optional local encrypted-body vault);
  it never calls Microsoft 365. Mailbox read-only posture is unchanged.

## Gate integration

`construction/data_quality/gates.py::_gate_email_classifier_persistence` already scans
`email_model_classifications`. No gate code change was needed — with rows present the gate
moves from `deferred_not_blocking` (observed=false) to `pass` (observed=true). The
no-writeback / no-secret / no-raw-body prover (`data_quality/safety.py`) continues to scan
the Phase 07A V20/V21 tables only; extending it to the V14/V23 tables is **deferred to Phase
07B Prompt 12** and tracked there.

## Evidence

`docs/evidence/construction-intelligence-phase-07b-calendar-email/06-email-classifier-persistence-proof.json`
(local validation) and `…/06-email-classifier-persistence-proof.md` (live real-store proof,
redacted).
