# Phase 10H — Tropical Source-Card Identity Reconciliation + Duplicate-Review Inventory

Deterministic cleanup that generalizes the 10G (email-only) block-authoritative identity reconcile to
**all** Tropical Work source cards, and produces a **count-only** duplicate-review inventory. No Qwen,
no graph apply, no new cards, no source indexing/read, no attachment extraction, no advisory summaries,
no duplicate consolidation/delete/merge/rename/move, no DB or runtime-JSON mutation.

## What changed in the corpus (live apply)

| Metric | Count |
|---|---|
| Tropical Work cards selected / scanned | 103 |
| Cards with exactly one Tropical identity block | 103 |
| Cards disagreeing (frontmatter or visible text) | 93 |
| Cards corrected | 93 |
| — non-email corrected | 93 |
| — email corrected | 0 |
| Frontmatter disagreements fixed | 93 |
| Visible "## Related Project" disagreements fixed | 91 |
| Project tags added | 0 (all cards already tagged) |
| Skipped: no id block / ambiguous / other project | 0 / 0 / 0 |

The 10 email cards reconciled in Phase 10G were already consistent and were **not re-touched**
(byte-identical), per amendment 1.

## Safety invariants (all verified)

- `db_mutations` = 0 (db meta_sha12 `31dce7a78878` unchanged before/after)
- `queue_delta` = 0 · `ollama_calls` = 0 · `new_cards` = 0 · `created`/`deleted` = 0
- `links_added` = 0 · `links_removed` = 0 · `offending_links_remaining` = 0
- Independent backup-vs-current diff over all 93 written cards:
  - **0** managed-block or out-of-scope changes (only `project_key` / `project_number` /
    `project/23-435-01` tag / the visible Related Project line differ)
  - 0 cards still carrying the "no project record linked yet" placeholder
  - 0 cards with a missing/wrong `project_key` (all now `tropical`)
  - 0 cards with != 1 identity block
- Idempotence: a post-apply `--dry-run` reports **0** disagreeing across all 103 cards.

## Duplicate-review inventory (count-only; created/changed nothing)

| Signal | Count |
|---|---|
| Duplicate-review pairs (unique) | 28 |
| — same source SHA-256 | 28 |
| — same email message-id | 1 |
| — same attachment SHA-256 | 0 |
| Duplicate clusters | 4 |
| Largest cluster size | 7 |

A pair sharing multiple duplicate signals is counted once in the unique-pair total while contributing
to each applicable per-signal count. Per-pair / per-cluster detail (12-char id hashes only) lives under
`local-sensitive/` (git-ignored) and is not committed. This inventory is informational for a later
Phase 10I duplicate-cluster review; **no** consolidation/deletion/merge is performed here.

## Backend handling

The `:8000` backend was owned by another worktree (`verify/schedule-named-baseline-phase13d`). With
user approval it was stopped (SIGTERM), the WAL checkpointed (TRUNCATE), the applier run unsandboxed,
then the backend was **restarted faithfully** from its original worktree cwd + env and confirmed
serving.

## Artifacts

- `00-repo-truth-audit.txt` — change scope + reused-unchanged inventory
- `01-runtime-preconditions.txt` — flags/queue/backend/baselines
- `phase10h-apply-summary-safe.json` — count-only apply result
- `local-sensitive/` (git-ignored) — dry-run/apply detail rows + full rollback backups of the 93 cards
