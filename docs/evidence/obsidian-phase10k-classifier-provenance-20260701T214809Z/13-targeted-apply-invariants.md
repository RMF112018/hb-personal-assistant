# Phase 10K — Targeted apply invariants (3 known cards)

Backend `:8000` (schedule-verify worktree) stopped for the apply and restarted faithfully afterward.
Apply scope was exactly the three known cards (`--note-rel` ×3); the broader Tropical corpus was
dry-run/visibility only (amendment 6).

## Apply result (safe / count-only — see 12-targeted-apply-summary.json)
- cards_scanned: 3, cards_with_conflict: 3, repairs_planned: 3, repairs_applicable: 3
- cards_modified: 3, skipped: 0, review_required: 0
- from → to: warranty→value_analysis, submittal→specification_template, scope_of_work→clarification_memo
- ollama_calls: 0

## Invariants (whole run)
- db_mutations: 0, queue_delta: 0, created: 0, deleted: 0
- DB fingerprint unchanged before/after; queue unchanged.

## Per-card verification (independent re-read; details under local-sensitive/)
For each of the 3 cards:
- frontmatter `document_type` and the `source/type/*` tag updated to the repaired type/slug.
- Why This Matters / PM Review Cues regenerated from the repaired type's deterministic guidance.
- Source Basis "Document type" + "Classification reason" carry the Phase 10K provenance note.
- `hb-local-summary` and `hb-project-identity` blocks byte-identical to the pre-apply backup.
- `source_id`, `source_sha256`, `source_path`, `source_mtime_ns`, `generated_at`, `indexed_at`
  unchanged.
- Summary/classifier consistency preserved: the 10J-corrected generated summaries already assert the
  true nature (value-analysis / generic spec template / clarification memo), so none were skipped with
  `summary_refresh_required`, and the repaired frontmatter now agrees with the summary.

## Reversibility & idempotency
- Pre-apply backups of all 3 cards under git-ignored `local-sensitive/backups/classifier_repair/`.
- Re-running the dry-run on the repaired cards yields repairs_planned=0, cards_with_conflict=0
  (idempotent).
