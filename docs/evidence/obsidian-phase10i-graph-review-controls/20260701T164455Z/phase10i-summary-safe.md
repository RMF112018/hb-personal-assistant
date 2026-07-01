# Phase 10I — Graph Review + Operator Controls (READ-ONLY) — Summary (safe / count-only)

Read-only operator review surfaces over the bounded Tropical source-card graph. Computes counts +
distributions and a design spec for future operator controls. Executes nothing: no graph link/tag
apply/removal, no duplicate delete/merge/rename/move, no identity write, no card generation, no source
indexing, no attachment extraction, no advisory summaries, no Qwen/Ollama, no DB write, no runtime-JSON
write. Review state is file/report only.

## New surface
`scripts/obsidian_source_graph_review.py` — modes `--duplicate-clusters` / `--relationship-candidates`
/ `--existing-links` / `--identity-quality` / `--isolated-high-value` / `--all`; `--json-output` +
`--markdown-report`; `--dry-run` (default) vs `--write-review-report` (evidence only). Reuses the
10C/10G/10H engine + selection + inventory + identity helpers unchanged. Only reads generated Work
cards (via the DB index) + read-only DB counts — never original sources/attachments/.eml/Email Archive.

## Live read-only run (bounded Tropical 23-435-01 / tropical / 2525840)

| Surface | Result |
|---|---|
| Cards checked | 103 |
| Identity consistent / inconsistent | 103 / 0 |
| Ambiguous / missing / non-Tropical id blocks | 0 / 0 / 0 |
| Duplicate-review pairs (source / email / attachment) | 28 (28 / 1 / 0) |
| Duplicate clusters (size 2 / 3–5 / 6+; largest) | 4 (1 / 2 / 1; 7) |
| Existing graph blocks / relationships | 0 / 0 |
| One-way links / reciprocal pass | 0 / true |
| Invalid types / durable same_project / durable duplicate / invalid tags | 0 / 0 / 0 / 0 |
| Candidate pairs (default) / primary+secondary eligible | 5225 / 3 |
| Project-only rejected / weak-only rejected | 5178 / 0 |
| Isolated cards / isolated high-value | 103 / 66 |
| Isolated email / attachment / submittal-or-rfi | 10 / 2 / 2 |

Identity and duplicate counts reproduce the post-10H corpus exactly. In a single bounded project nearly
every pair shares a project signal, so default-mode candidates are near-universal (5225) while only 3
pairs meet the durable primary+secondary rule — this is why project signals are context-only and durable
links require a primary signal. No `gc-graph-links` exist yet, so all 103 cards are "isolated".

## Read-only guardrails (proved pre/post)

`cards_modified` = 0 · `db_mutations` = 0 · `queue_delta` = 0 · `runtime_json_mutated` = false ·
`ollama_calls` = 0. Proof: DB fingerprint, queue counts, per-card SHA256, and config-file SHA compared
before/after the review; any delta raises a read-only-invariant refusal. Backend `:8000` (owned by
another worktree) was left running; the review needs no backend-down and made no writes.

## Operator control design (Phase 10J — listed, executed here: none)

- **Duplicate:** mark_duplicate, mark_not_duplicate, choose_canonical, defer, merge_later, delete_later
- **Relationship:** accept_relationship, reject_relationship, defer_relationship, rollback_relationship,
  explain_relationship
- **Identity:** mark_identity_verified, mark_identity_wrong, request_reconcile
- **Rollback:** preview_rollback, apply_rollback, export_rollback_bundle

## Artifacts
- `00-repo-truth-audit.txt` — change scope + reused-unchanged inventory
- `01-runtime-preconditions.txt` — flags/backend/live counts + read-only invariants
- `phase10i-review-summary-safe.json` — count-only machine result
- `phase10i-review-report-safe.md` — rendered count-only review report
- `local-sensitive/` (git-ignored) — per-cluster/per-pair/per-link detail rows (12-char id hashes only)

## Validation
2 new test files (20 tests) + existing applier review-report test (unchanged) + full obsidian_source
suite green; ruff clean; safe evidence count-only; `local-sensitive/` untracked.
