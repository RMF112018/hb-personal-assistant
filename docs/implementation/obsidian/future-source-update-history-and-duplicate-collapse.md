# Future: Source Update History + Duplicate Collapse (Phase 10L-D / 10L-E)

**Status: NOT implemented in Phase 10L.** Phase 10L (A+B+C) does not add any schema, canonicalization
behavior, duplicate managed block, or update-history block. Duplicate detection in this pass is
**advisory / read-only** — the reconcile tool reports duplicate-content card groups count-only. This
document records the approved design so a later phase can implement it.

## Approved duplicate-collapse design (hybrid grouping — Bobby, 2026-07-02)

Do **not** re-key `source_id`. It stays path/source-record identity
(`source_id_for = sha256("{kind}|file|{rel_path}")[:32]`). Instead introduce a grouping layer:

1. Detect duplicate content groups by `content_sha256` plus supporting metadata (attachment sha,
   document number) — reuse `source_note_graph.DUPLICATE_SIGNALS` / `is_duplicate_pair`.
2. Select one **canonical** card per group, preferring the newest metadata/content version.
3. Suppress creation of additional cards for the duplicate source rows.
4. Add/update an `hb-duplicate-source-group` managed block on the canonical card.
5. Preserve every source row and `source_id` in the DB.
6. Link duplicate source rows to the canonical generated card via **new additive** columns
   `duplicate_group_id` / `canonical_generated_note_id` (a `V98` migration — additive only, per the
   store's never-rewrite rule).
7. Do **not** run a broad historical migration until dry-run evidence proves the grouping behavior on a
   bounded corpus.

Proposed managed block:

```text
<!-- hb-duplicate-source-group:start -->
Status: canonical
Primary source version: newest
Duplicate source count: <count>
Most recent metadata timestamp: <timestamp>
Content comparison: unchanged | metadata-only | changed
Review required: yes | no
<!-- hb-duplicate-source-group:end -->
```

## Update-in-place history (Phase 10L-E)

The watchdog already updates a card in place (stable path→`source_id`, `upsert`, `overwrite=True`), but
`replace_local_summary_block` *replaces* the single `hb-local-summary` block. The future work adds
append-only history:

```text
<!-- hb-source-change-log:start -->
- <timestamp> — version <n>; content_sha_changed=<yes/no>; metadata_changed=<yes/no>; summary_status=<status>
<!-- hb-source-change-log:end -->
```

```text
<!-- hb-local-summary-history:start -->
### <timestamp> — qwen2.5:14b
<validated dated summary>
<!-- hb-local-summary-history:end -->
```

Prior summaries are retained; each change appends (never replaces). No duplicate generated-note row and
no duplicate markdown card may be created.

## Explicitly out of scope for Phase 10L

- No `duplicate_group_id` / `canonical_generated_note_id` columns (no `V98`).
- No `hb-duplicate-source-group` / `hb-source-change-log` / `hb-local-summary-history` writers.
- No canonical-card suppression. Reconcile only *reports* duplicate groups count-only.
