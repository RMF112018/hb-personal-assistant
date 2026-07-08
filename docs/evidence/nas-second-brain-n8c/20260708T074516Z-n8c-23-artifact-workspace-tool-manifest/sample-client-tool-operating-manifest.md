---
note_type: client_tool_operating_manifest
manifest_version: 1
generated_at: '2026-07-08T00:00:00+00:00'
generated_from_runtime_commit: n8c23-evidence
checksum: 508bc40f8584ec1da9d1f00b
staleness_state: fresh
next_review_due_at: null
tags:
- second-brain/canonical
- topic/nas-mcp
- topic/structured-intelligence
- phase/n8c-23
---

# Client Tool Operating Manifest

Tools: 4 · Workflows: 4 · Mappings: 5 · Staleness: **fresh**

## Preferred tool hierarchy

- Normal second-brain questions → structured `assistant_*` tools first.
- Source discovery → `assistant_source_*` tools first.
- Durable memory creation → `pa_artifact_proposal_stage` → review → promotion.
- Canonical memory → validate + `pa_artifact_promotion_apply` (operator-approved).
- Auditing → receipts + manifests.
- Low-level vault/root/DB tools only when explicitly requested.

## Tools

| tool | class | read/write | safety |
|---|---|---|---|
| `hb_mcp_status` | read_only_status | read_only | safe_read |
| `pa_artifact_promotion_apply` | canonical_promotion | canonical_write | canonical_promotion_requires_explicit_approval |
| `pa_session_capture_stage` | staged_write | staged_write | staged_write_requires_review |
| `pa_tool_manifest_get` | manifest_lookup | read_only | bounded_read |

## Replacement map

- instead of `hb_root_search` → assistant_source_file_search
- instead of `hb_root_read_file` → assistant_source_file_read
- instead of `search_vault` → assistant_search_sources
- instead of `hb_db_select` → assistant_* semantic retrieval tools
- instead of `direct_note_creation` → pa_artifact_proposal_stage → review → pa_artifact_promotion_apply

## Do not

- do not use low-level vault search as the first step for ordinary structured-intelligence queries
- do not use root file tools for canonical artifact retrieval when semantic tools exist
- do not promote artifacts without explicit operator approval
- do not create canonical records directly
- do not write arbitrary notes into the vault
- do not bypass staging/review/versioning
- do not treat advisory tools as execution tools
- do not treat action-stage records as permission to execute
- do not silently merge duplicate decisions/preferences/open-loops
- do not use receipt tools as primary semantic retrieval unless auditing promotion history

## Workflow recipes

### document_session
- triggers: document this session, record our discussion, save the key points, turn this into second-brain artifacts, capture the decisions from this chat
- sequence: pa_session_capture_stage → pa_artifact_proposal_stage → pa_artifact_proposal_list → pa_artifact_proposal_review → pa_artifact_proposal_revise → pa_artifact_proposal_plan_promotion → pa_artifact_promotion_validate → pa_artifact_promotion_apply → pa_artifact_promotion_receipt_get
- approval points: pa_artifact_proposal_review, pa_artifact_promotion_apply

### find_source_file
- triggers: find the file, search my documents, look in the project folder
- sequence: assistant_source_file_search → assistant_source_file_metadata → assistant_source_file_read → assistant_get_card_for_source
- approval points: none

### retrieve_decision
- triggers: what did we decide, find the decision
- sequence: pa_canonical_artifact_list → pa_canonical_artifact_get → assistant_list_decisions
- approval points: none

### check_tool_manifest_freshness
- triggers: is the tool map current, check tool manifest
- sequence: pa_tool_manifest_freshness_check → pa_tool_manifest_review_plan
- approval points: pa_tool_manifest_refresh_promote

