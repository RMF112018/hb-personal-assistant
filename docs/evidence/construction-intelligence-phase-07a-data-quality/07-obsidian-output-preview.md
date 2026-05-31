# Obsidian Data Quality Outputs — Dry-Run Preview (Phase 07A Prompt 06)

Generated: 2026-05-31T09:47:29.985270+00:00
Repo SHA: ff047028a7edb8085e5fc0bdf76a776aa6764095
Schema: V0

## Project Data Quality Summary (excerpt)

---
phase: 07A
generated_utc: 2026-05-31T09:47:29.985270+00:00
repo_sha: ff047028a7edb8085e5fc0bdf76a776aa6764095
schema_version: 0
source_systems:
  - procore
  - email
  - graph_files
  - construction_store
writeback: none
raw_body_persisted: false
raw_document_text_persisted: false
marker_bounded: true
---
# Project Data Quality Summary (Phase 07A)
Generated: 2026-05-31T09:47:29.985270+00:00 | Repo: ff047028 | Schema: V0

## Source Coverage by Project
_No project coverage data present in local marts (V21). Run data-quality marts first._

> Guardrail: This summary contains only aggregate counts and redacted metadata. No raw content.


---

## Source Record Map Register (excerpt)

---
phase: 07A
generated_utc: 2026-05-31T09:47:29.985270+00:00
repo_sha: ff047028a7edb8085e5fc0bdf76a776aa6764095
schema_version: 0
source_systems:
  - procore
  - email
  - graph_files
  - construction_store
writeback: none
raw_body_persisted: false
raw_document_text_persisted: false
marker_bounded: true
---
# Source Record Map Register (Phase 07A)
Generated: 2026-05-31T09:47:29.985270+00:00 | Total mapped rows shown (capped): 0

_No rows in source_system_record_map. Run data-quality source-record-map --apply to populate._

Model-proposed, weak, or sensitive relationships are never promoted as authoritative. They appear only in review queues with explicit review_required=true.

> Guardrail: Only title_redacted and canonical IDs (no bodies, no URLs, no secrets).


---

## Relationship Diagnostics (excerpt)

---
phase: 07A
generated_utc: 2026-05-31T09:47:29.985270+00:00
repo_sha: ff047028a7edb8085e5fc0bdf76a776aa6764095
schema_version: 0
source_systems:
  - procore
  - email
  - graph_files
  - construction_store
writeback: none
raw_body_persisted: false
raw_document_text_persisted: false
marker_bounded: true
---
# Relationship Diagnostics Register (Phase 07A)
Generated: 2026-05-31T09:47:29.985270+00:00

## Quality Summary (from relationship_quality_mart)
_No relationship quality mart rows (run data-quality marts)._

## Review Candidates (from relationship_resolution_queue)
_No queued candidates._

Model-proposed, weak, or sensitive relationships are never promoted as authoritative. They appear only in review queues with explicit review_required=true.

> Guardrail: Zero raw content. Candidates with review_required=true are never auto-promoted.


---

## Phase Gate Summary (excerpt)

---
phase: 07A
generated_utc: 2026-05-31T09:47:29.985270+00:00
repo_sha: ff047028a7edb8085e5fc0bdf76a776aa6764095
schema_version: 0
source_systems:
  - procore
  - email
  - graph_files
  - construction_store
writeback: none
raw_body_persisted: false
raw_document_text_persisted: false
marker_bounded: true
---
# Phase 07A Gate Summary / Readiness Snapshot (Phase 07A)
Generated: 2026-05-31T09:47:29.985270+00:00 | Schema V0

This is a **readiness snapshot** derived from local marts. Full gates with thresholds and go/no-go are in Prompt 07.

## Cross-Domain Readiness (from cross_domain_context_readiness_mart)
_Readiness table not present or empty (V21 migration pending)._ 

## Key Guardrails Attestation
- external_systems: read_only
- writeback: local_vault_only_on_apply
- raw_body_persisted: False
- raw_document_text_persisted: False
- tokens_or_urls_in_output: False
- source_file_copies: False
- candidate_relationships_promoted: False
- human_review_required_for_sensitive: True
- marker_bounded: True
- frontmatter_complete: True

Model-proposed, weak, or sensitive relationships are never promoted as authoritative. They appear only in review queues with explicit review_required=true.

> This note is marker-bounded and safe to re-render. User content outside markers is preserved.


---

> Full rendered sections use marker-bounded writes. This preview is for evidence only.
