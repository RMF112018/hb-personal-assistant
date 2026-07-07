# 06 — Bounded Artifact Policy + Conservative Classification

## Copied-field whitelist (bounded scalars only)
Handlers copy upstream records ONLY through `bounded_metadata(record, whitelist)`, which keeps whitelisted
SCALAR fields and **drops any key ending in `_json`** (defense-in-depth). The whitelists are the vetted
N8C-15 sets (`_PACK_WL/_PROJECTION_WL/_PACKET_WL/_DRAFT_WL/_DECISION_WL/_PREFERENCE_WL/_OPEN_LOOP_WL/_NODE_WL/
_REVIEW_WL/_CITATION_WL/_SOURCE_REF_WL`) plus two new N8C-17 sets:
- `_CLAIM_WL` — `claim_id, claim_type, status, review_state, source_state, confidence, card_id, source_id,
  source_root_key, source_rel_path, note_rel_path, created_at`. **Deliberately excludes `claim_text` and
  `evidence_excerpt`** — a claim is surfaced as a bounded REFERENCE, never its body.
- `_SOURCE_FILE_WL` — `source_ref, source_id, source_root_key, rel_path, source_kind, extension, mime_type`.
  **Excludes the FTS `snippet`** — no content excerpt is copied.

**Never copied:** `section_body`, `evidence_excerpt`, `claim_text`, any `*_json`/`metadata_json`/
`result_json` blob, full packet/draft/pack exports, raw bodies, raw prompts/responses, full upstream
payloads, FTS snippets. Proven across all four workflows (with a seeded claim carrying `SECRET CLAIM BODY` /
`SECRET EVIDENCE EXCERPT`) by:
- `test_workflow_handlers.py::test_no_raw_bodies_or_blobs[*]` (all four)
- `test_workflow_handlers.py::test_project_intelligence_claim_bodies_never_leak`
- `test_workflow_handlers.py::test_source_files_carry_bounded_metadata_never_snippet`
- `test_workflow_router.py::test_envelope_carries_no_raw_bodies_or_payloads`
- `test_nas_mcp_workflows.py::test_route_and_context_return_workflow_sections_for_implemented_workflows`

## Conservative review-state classification (clarification #8)
`_classify(rec)` derives a bucket from a review overlay (`effective_state`/`review_state`) if present, else
the record's own `status`:
- **trusted:** `accepted`, `operator_accepted`, `trusted`, `effective_support`, `supported`, `approved`
- **excluded:** `rejected`, `operator_rejected`, `not_required`, `superseded`, `stale`, `obsolete`,
  `excluded`, `withdrawn`
- **candidate (default):** `candidate`, `unreviewed`, `needs_review`, `deferred`, … and **anything missing,
  unknown, or contradictory** (a token set that is both trusted AND candidate falls to candidate).
- **overlay wins:** a review overlay overrides the record's own status (so a `status=accepted` record with
  `review_state=operator_rejected` is EXCLUDED, and one still `unreviewed` is CANDIDATE, never trusted).

Rejected/superseded/stale content therefore never populates a trusted section, and candidate content is
always labeled. Proven by the 16-case `test_classify_is_conservative` parametrization plus the per-handler
split assertions (`test_daily_brief_sections_present_and_split`,
`test_project_intelligence_sections_and_scope`, `test_open_loop_triage_buckets`).
