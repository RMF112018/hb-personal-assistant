# Phase 10A Candidate Review CLI — No-Raw / No-Writeback Proof

**Date:** 2026-06-08
**Scope:** Guardrail proof coverage for the Phase 10A candidate review surface
(service `local_ai/candidate_review.py` + the `second-brain review` CLI verbs).
**Result:** PASS — review actions are local DB updates only; no raw content is read
or emitted; no external writeback path is imported or called; guard columns stay 0.

This is a hand-authored attestation (companion to `00-rebaseline.md`). It maps each
required proof-scope item to the test that proves it. No proof-builder module or CLI
proof command was added this phase — the existing repo-wide scan already covers the
new module structurally (see §3).

## 1. Required proof scope → proving test

| Required proof | Proven by |
|---|---|
| Candidate review **output** contains no raw email body/prompt/response | `test_no_forbidden_keys_in_any_output` (service), `test_review_cli_outputs_have_no_raw_keys` / `test_review_action_outputs_have_no_raw_keys` (CLI) — recursive scan of every emitted payload for forbidden keys |
| Candidate review **persisted rows** contain no raw body/prompt/response/URL/token | `test_no_raw_persisted_in_candidate_review_tables` — after accept + edit + snooze, scans every TEXT cell of `task_candidates`, `commitment_candidates`, `candidate_review_events`, `candidate_source_refs` for `http://` / `https://` / `-----BEGIN` / `PRIVATE KEY` / `access_token` / `bearer ` |
| Review state transitions do **not** call Graph/Procore/email/calendar write paths | `test_candidate_review_and_cli_import_no_external_write_surface` — AST-imports of the service module **and** the review CLI functions/helpers carry no forbidden external-write / raw-exposure module (`graph`, `procore`, `msal`, `requests`, `httpx`, `urllib`, `smtplib`, `aiohttp`, `boto`, `mcp`, `packet_builders`) |
| Guard columns remain zero after review actions | `test_guardrail_columns_stay_zero_after_review_ops` — the 13 `PHASE_10_GUARD_COLUMNS` sum to 0 across `task_candidates`, `commitment_candidates`, `candidate_review_events` after accept + edit + snooze |
| Export is redacted/safe | `test_export_returns_safe_items_with_refs`, `test_review_export_cli_to_file_and_stdout` — the exported file + stdout payload pass the recursive no-forbidden-key scan |

## 2. Guard-column attestation

The 13 `_P10_GUARDS` CHECK columns (`raw_email_body_persisted`,
`raw_document_text_persisted`, `raw_calendar_payload_persisted`,
`raw_procore_payload_persisted`, `raw_prompt_persisted`, `raw_response_persisted`,
`signed_url_persisted`, `download_url_persisted`, `external_writeback_performed`,
`graph_writeback_performed`, `procore_writeback_performed`, `email_send_performed`,
`calendar_mutation_performed`) are pinned to 0 by the schema `CHECK` constraints and
are never written by the review store methods. Behaviorally confirmed zero after
review operations.

## 3. Structural coverage (already in place)

`build_second_brain_no_writeback_proof` (exercised by
`tests/test_second_brain_no_writeback_proof.py`) dynamically enumerates **every**
`construction/second_brain/**/*.py` and scans for mutation patterns, dangerous
HTTP/SDK imports, and secrets. Because `local_ai/candidate_review.py` lives under
that tree, the review service is already inside that repo-wide proof — and it passes.
The Prompt 08 tests above add the **named, review-specific** assertions on top.

## 4. Validation command

```
pytest tests/test_phase_08d_no_raw_access.py tests/test_phase_08d_no_writeback.py \
       tests/test_second_brain_no_writeback_proof.py \
       tests/test_phase_10a_candidate_review.py tests/test_phase_10a_candidate_review_cli.py
```

**Result:** 66 passed (was 64; +2 Prompt 08 proofs). `ruff` clean.

## 5. Guardrails reaffirmed

No email send · no calendar mutation · no Graph writeback · no Procore writeback ·
no external/cloud LLM dependency · no raw email body / document text / calendar /
Procore payload / prompt / response / signed URL / download URL / token / secret
persisted or emitted. Review actions are local SQLite updates only; source refs are
immutable. The proofs scan for — and never echo — offending text.
