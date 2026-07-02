# Phase 10K.1 — Post-Repair Polish (3 targeted cards)

Deterministic follow-up to the Phase 10K classifier repair. The repair corrected
`document_type` / `source/type/*` / Why / Cues / Source Basis but left the `## Follow-Up`
section and topical `related/*` tags carrying pre-repair provenance. This polish regenerates
Follow-Up from the repaired type's deterministic `_PM_GUIDANCE`, prunes ungrounded topical
`related/*` tags, and applies review-tag changes **only where justified by the repaired type**.

No model call, no source-file read, no DB write, no managed-block / identity / graph-link
mutation, no `document_type` / `source/type/*` change. Apply is bounded to exactly the three
`--note-rel` cards.

## Artifacts (safe / count-only)

| file | what |
|---|---|
| `phase10k1-polish-dryrun-safe.{json,md}` | dry-run over the 3 cards (wrote nothing) |
| `phase10k1-polish-apply-safe.{json,md}` | targeted apply (3 cards modified, invariants 0) |
| `phase10k1-polish-idempotency-safe.{json,md}` | re-run apply → all change counts 0 |
| `local-sensitive/` | **git-ignored** — before/after bodies, backups, per-card detail |

## Results

Dry-run == apply: `cards_scanned 3, cards_changed 3, followup_updated 3, related_tags_pruned 2,
review_tags_added 1, review_tags_removed 1, review_tags_skipped 4, db_mutations 0, ollama_calls 0`,
all invariants 0. Idempotency re-run: `cards_changed 0, followup_updated 0, related_tags_pruned 0,
review_tags_added 0, review_tags_removed 0`, invariants 0.

Per-card outcome (verified on disk vs backups — managed blocks + source id/sha/path/timestamps
byte-preserved):

- **VA log** (`value_analysis`): kept `related/project` + `review/project-context`; Follow-Up
  replaced with VA-log items (pending/conditional items, #REF/value issues, budget/change docs).
  Review add/drop **gated out** (not justified for `value_analysis`).
- **Specification template** (`specification_template`): pruned `related/submittal`; dropped
  `review/metadata-only`; added `review/project-context`; Follow-Up → adopted / edited /
  superseded template question.
- **Clarification memo** (`clarification_memo`): pruned `related/scope`; kept
  `review/project-context`; Follow-Up → responses / decision owners for open items. Review
  add/drop **gated out** (not justified for `clarification_memo`).

The `--add-review` / `--drop-review` flags are filtered per card against a type-keyed justified
map (`_REVIEW_ADD_JUSTIFIED` / `_REVIEW_DROP_JUSTIFIED` in `source_card_repair.py`), so the one
invocation only mutates review tags on the spec card and can never become a broad, untyped
mutation path if the tool is reused. Cards carrying a `gc-graph-links` block are never pruned.
