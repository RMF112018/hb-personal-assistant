# 06 — Canonical Source Registry Projection Proof

**Prompt:** Prompt 03 — Canonical Source Registry Projection
**Phase:** HB Construction Intelligence Phase 06 — SharePoint / OneDrive File Intelligence
**Date:** 2026-05-30
**Posture:** Makes the V5 canonical source-location projection operator-reachable. Read-only against
Microsoft 365; no Graph calls; **no new migration, no scope change**. Permission tightening deferred.

---

## 1. Reconciliation — reuse vs. new

The V5 projection already existed in repo truth and is **reused**, not reimplemented:

- `construction/source_projection.py` → `project_registry_to_v5_source_locations(registry, store)`
  (idempotent upsert per source; compat-record handling; lossy-field accounting).
- `ConstructionStore.upsert_source_location()` → `INSERT … ON CONFLICT(source_id) DO UPDATE` into
  the V5 `construction_source_locations` table.
- Read-only enforced at three layers: model `read_only: Literal[True]`, store `ValueError` guard,
  SQLite `CHECK(read_only = 1)`.

**Gap closed this prompt:** the projection was not reachable from the operator surface (the resolver
writes only the V2 `construction_source_resolutions`). Prompt 03 adds:

1. A `dry_run` mode on the projection function (same `ProjectionReport`, **no** SQLite write;
   `store` optional). Backward compatible with existing positional callers.
2. A dry-run-default `hb-assistant graph files sources [--apply] [--json]` command.

The package's proposed `phase_06_*_schema_proposal.sql` (6 new ingestion/download/extraction tables)
and policy seed template are **deferred** to the prompts that need them (P07/P10–12); the existing
V5 schema fully supports this prompt. Additive-only rule honored — nothing rewritten.

---

## 2. Dry-run projection (no SQLite write) — `graph files sources --json`

```json
{
  "command": "graph files sources",
  "mode": "dry_run",
  "ok": true,
  "summary": {
    "total": 14,
    "by_system": {"sharepoint": 10, "onedrive_personal": 2, "onedrive_business": 1,
                  "onedrive_shared_libraries": 1},
    "by_scope": {"sharepoint_site": 2, "onedrive_personal": 1,
                 "sharepoint_project_drive_folder": 7, "sharepoint_site_page": 1,
                 "onedrive_business_root": 1, "onedrive_personal_root": 1,
                 "onedrive_shared_library": 1},
    "enabled": 14, "disabled": 0,
    "pre_resolved": 7, "pending": 7,
    "matched": 8, "unmatched": 2,
    "review_required": 2,
    "projected": 11, "compat_projected": 3, "skipped": 0
  },
  "persisted_source_location_count": null,
  "guardrails": {"external_systems": "read_only", "writeback": "none", "metadata_only": true,
                 "all_read_only": true, "permission_tightening": "deferred"}
}
```

Validation of the 14 seed sources:

- **enabled:** 14 / 0 disabled.
- **pre-resolved:** 7 (carry `drive_id`/`site_id`/`folder_item_id` or `resolution_status` in
  {graph_delta_ready, resolved}) — incl. `sp_2023projects_23_435_01_tropical_sl` (graph_delta_ready).
- **pending:** 7 (`resolution_status` starts with `pending`; no Graph IDs yet) — the 3 Phase 01
  compat records + the site-page + the 3 OneDrive roots/shared library.
- **unmatched → review:** 2 (`sp_2026projects_26_727_01_wellington_marketplace_condo_hotel`,
  `sp_2026projects_26_898_01_wellington_townhomes`), both `review_required`.
- **projected / compat:** 11 canonical + 3 Phase 01 compat records.

`persisted_source_location_count: null` confirms dry-run wrote nothing.

---

## 3. Apply + idempotency — `graph files sources --apply`

Run against the local construction store (the operator outcome; benign, local SQLite only):

```
apply #1 → mode=apply ok=true persisted=14
apply #2 → mode=apply ok=true persisted=14   (idempotent: count stable, no duplicates)
```

Test-isolated idempotency (`tests/test_source_registry_projection.py`): apply on a temp DB yields 14
rows; re-apply keeps 14 with identical `source_id` set. Dry-run on a temp DB leaves
`list_source_locations()` empty.

---

## 4. Invalid read_only / policy rejection

| Attempt | Layer | Result |
| --- | --- | --- |
| `SourceLocation(read_only=False)` | model `Literal[True]` | `ValidationError` |
| `DefaultPolicies(copy_originals_to_vault=True)` | model validator | `ValidationError` |
| `DefaultPolicies(store_full_text_in_vault_notes=True)` | model validator | `ValidationError` |
| `FolderPolicies(deep_index_allowed=["Contracts"], review_required=["contracts"])` | model validator | `ValidationError` (no silent deep-index of review-required) |
| `ConstructionStore.upsert_source_location(read_only=False)` | store guard | `ValueError("read_only must be True")` |
| (DB layer) any `read_only != 1` | SQLite `CHECK(read_only = 1)` | rejected |

All covered by `tests/test_source_registry_projection.py`.

---

## 5. SourceLocation → V5 column mapping (reused)

`source_key→source_id`, `kind→source_scope`, `display_name→source_name`,
`source_system` (inferred from kind for compat records), `root_path→folder_path`,
`page_url→folder_web_url` (sharepoint_site_page only), `baseline_policy`/`folder_policies` →
`*_json` (deterministic dumps). Lossy (registry remains source of truth): `crawl_mode`,
`indexing_depth`, `match_status`, `match_confidence`, `review_required`, `baseline` snapshot.

---

## 6. Validation recorded

- `ruff check .` PASS (`ruff format` applied to `cli/graph.py` + `source_projection.py`);
  `mypy src` PASS (130 files); `compileall` PASS.
- `pytest tests/test_source_registry_projection.py tests/test_construction_sources.py
  tests/test_mutation_lockout.py tests/test_graph_files_endpoint_guard.py` → all green.
- Full default-safe suite unchanged except additions: still only the pre-existing 12 email-track
  failures; **no new failures**.

---

## 7. Stop-Condition Check

No stop condition triggered. No Microsoft 365 writeback, no permission tightening, no source-file
copy into Obsidian, no full source text persisted, no raw delta links, no review-routing bypass
(the two unmatched sources are surfaced as `review_required`). Projection writes only to the local
canonical `construction_source_locations` table; dry-run is the default.
