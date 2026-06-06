# 174 — Phase 09 Addendum: Daily Brief Output Receipts & Optional Import Policy

**Status:** New governance: output-class definitions, a metadata-only output-receipt builder, and a deferred-import policy.
**Schema:** unchanged (V39; no migration; no persistence to trusted stores). **Version:** 1.4.0-phase-09-addendum (package: Daily Brief / MCP Handoff & Rendering, Prompt 05 — closeout).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-daily-brief-mcp-handoff/daily-brief-output-receipt-policy.md`, `daily-brief-rendered-output-receipt-proof.{json,md}`.
**Builds on:** records 170 (packet), 171 (MCP tool), 172 (templates), 173 (rendered quality).

---

## 1. Objective

Define where daily-brief outputs live and prevent Claude-rendered narrative from contaminating trusted
retrieval/memory stores.

## 2. Output classes

- **Trusted packet** (`trusted_daily_brief_packet`) — application-generated `DailyBriefHandoffPacketV1`:
  metadata-only, source-linked, approved, MCP-safe, manifest-referenceable, regenerable. Location:
  `docs/evidence/.../retrieval-memory-quality/daily-brief-packets/` (or existing daily-brief path).
- **Rendered narrative** (`rendered_daily_brief_narrative`) — Claude scheduled-task output:
  human-readable, advisory, **not source truth**; not approved-memory / vector-index / source-linked-proof
  input. Location (corrected in Prompt 04 — see record 181): `<vault>/Work/Daily Brief/`.

## 3. Receipts

`daily_brief/output_receipt.py`: `build_trusted_packet_receipt` and `build_rendered_brief_receipt`
produce metadata-only receipts. The rendered receipt carries packet_id, packet_hash, rendered_file_path,
rendered_utc, renderer, validation_proof_status (from the Prompt-04 validator), and the attestations
`advisory_only=true`, `not_source_truth=true`, `imported_to_memory=false`,
`imported_to_vector_index=false`, `external_writeback=false`, `import_enabled=false`. No DB persistence.

## 4. Exclusion by construction

`rendered_daily_brief_narrative` is not in `ALLOWLISTED_SOURCE_FAMILIES` (the 10 retrieval families —
the superset of embeddable + manifest read-model + source-linked families) nor in the 4 approved-manifest
categories (`generated_outputs`, `approved_obsidian_outputs`, `reviewed_memory`, `approved_read_models`),
and accepted memory loads only `review_status='accepted'` items (`retrieval/memory_loader.py`) with no
rendered-brief memory type. The proof asserts each exclusion against those constants.

## 5. Deferred import

`import_rendered_brief(...)` fails closed (`RenderedOutputReceiptError`); `IMPORT_ENABLED = False`. A
later import would require explicit human review, source-link preservation, and
no-raw/no-writeback/no-determination proofs.

## 6. Proof, CLI & validation

`build_daily_brief_rendered_output_receipt_proof` (CLI `second-brain daily-brief output-receipt-proof`)
builds both receipts over a seeded sample packet and asserts: receipts no-raw; rendered not-source-truth;
excluded from vector index / accepted memory / source manifest / source-linked proof; import disabled &
deferred; no external writeback; receipt references the packet. `ruff`/`mypy` clean;
`tests/test_phase_09_daily_brief_output_receipt.py` (7) green; daily-brief + MCP suites green. The
pre-existing `test_phase_08d_schema_v37` lifecycle failure is unrelated (fails identically on clean `HEAD`).
