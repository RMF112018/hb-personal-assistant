# Phase 08A — Agent No-Raw-Content / No-Secret Proof (Prompt 15)

The no-secret / no-raw-content facet of `second-brain data-quality no-writeback-proof`.
Demonstrates that no secrets, tokens, signed/download URLs, PEMs, JWTs, or raw content
(prompts, model responses, email bodies, document text, calendar payloads) appear in the
Phase 08A module source, persisted tables, evidence tree, generated brief/handoff outputs, or
model receipts. Uses the shared high-precision secret scanner + URL / raw-email / iCal
content patterns; findings are labels + locations only (never the value).

## Checks (all passed)

| Check | Result |
| --- | --- |
| `module_secret_scan_08a` (51 modules) | passed — no secrets/tokens in source |
| `sqlite_content_leak_scan_08a_tables` (18 tables) | passed — no secret / URL / raw-email / iCal in any persisted string cell |
| `evidence_output_scan_08a` | passed — Phase 08A evidence tree carries no secrets/tokens |
| `obsidian_brief_output_scan` | passed — generated brief vault dir (`Work/HB Personal Assistant/12_Daily_Brief`) clean (absent = nothing to scan) |
| `generated_brief_handoff_scan` | passed — an in-memory dry-run `DailyBriefResult` + `DeliveryHandoffPayload` carries no secrets/raw |
| `model_receipt_metadata_only` | passed — a `build_model_call_receipt` over raw-prompt/response markers persists only hashes + token counts; **neither marker appears**; no model-call/agent-run receipt table exists |

## Model-receipt metadata-only proof

`build_model_call_receipt(input_context="RAWPROMPTMARKER…", output_text="RAWRESPONSEMARKER…")`
→ the serialized receipt contains `input_context_hash` + `output_hash` + token counts and
**neither raw marker** (`raw_markers_absent: true`, `hashes_present: true`). Model-call and
agent-run receipts remain in-memory only (V27-deferred); the proof asserts no
`second_brain_agent_model_receipts` / `second_brain_agent_run_receipts` table exists.

## Result

`second-brain-no-writeback-proof.json` → all no-raw-content checks `passed: true`; overall
`proof_passed: true`, `no_raw_values_persisted: true`. Fail-closed: a planted secret/URL in
any scanned surface (verified by `test_content_scanner_flags_planted_secret`) or a receipt
carrying raw content would fail the proof.
