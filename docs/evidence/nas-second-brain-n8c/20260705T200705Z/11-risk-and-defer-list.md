# 11 — Risk & Defer List

## Deferred (with rationale)
1. **Source-card frontmatter neutrality additions** (`managed_by`/`card_id`/`card_status` on cards) —
   **deferred.** Source-card frontmatter is **already neutral** (no `hb_` keys; the `hb-*` debt is in
   managed-block markers, tracked separately), so there is no debranding benefit. Adding fields touches
   `source_notes.py::_frontmatter`, a byte-locked surface consumed by ~40 test files. N8C-2 instead
   uses a **computed** `card_id` and the existing neutral frontmatter. Low-churn path for a future
   slice: add `managed_by: personal_assistant` first (substring-safe), then update exact-structure
   tests.
2. **Reverse-lookup index** `idx_si_gennotes_relpath` — deferred. `get_sources_for_note` is an
   unindexed scan; acceptable (one row per card). Adding the index is a migration → not taken.
3. **Local-summary neutral EMIT flip** — still N8C-1/N8C-2 carry-forward debt (dual-READ landed in
   N8C-1; emit flip remains deferred). Independent of identity hardening; not addressed here.

## Out of scope for N8C-2 (later slices)
No claim/decision/open-loop tables; no Qwen queue; no context packs; no frontend; no new MCP
read/navigation tools or DB-allowlist widening; no new remote write surface; no maintenance loops; no
schema migration (`LATEST_SCHEMA_VERSION` stays 99).

## Stop-condition check — none tripped
N8C-1 evidence corrected (revision 1); `c454a581` base available; no existing source card broken
(rendering byte-unchanged, 124 tests green); no broad migration; no raw/import DB mutation; duplicate
+ stale detection proven; no new remote write surface / broad DB-fs access; live `hb_*` MCP tools
unchanged; source-deleted handled read-only (revision 4); no secrets/raw-emails/private-paths in
evidence.
