# Phase 01 — Step 5: Source Manifests & Sync Receipts Preview

- Date: 2026-05-27
- Branch: `main`
- HEAD pre-change: `9ff7ed19568c7f0f216016d2a367165538985977`
- Prompt: 04 (build-sequence step 5)

## Purpose

Add deterministic, **projection-only** Markdown renderers and a `construction-agent sync` orchestrator on top of the V2 SQLite tables introduced in step 4. SQLite remains authoritative for sync state; Markdown is a recomputable human-readable view. No state lives only in Markdown.

## Implementation Summary

| Path | Action |
| --- | --- |
| `src/hb_assistant/construction/manifests/{__init__,models,renderer,service,vault_writer}.py` | created |
| `src/hb_assistant/construction/store/repositories.py` | edited (added `list_inventory_changed_since`) |
| `src/hb_assistant/cli/construction.py` | edited (added `sync` command and supporting imports) |
| `resources/templates/{source_manifest,sync_receipt,processing_receipt}.template.md` | created |
| `tests/test_construction_manifests.py` | created (19 tests) |
| `docs/evidence/construction-intelligence-phase-01/04-source-manifest-and-sync-receipt-preview.md` | created (this file) |

No new third-party dependencies. No changes to `MarkerBoundedWriter`, `obsidian/`, `PathPolicy`, or any AppConfig/PathsConfig defaults. Templates use plain Python `str.format`. The construction-vault root is resolved from the `HB_CONSTRUCTION_VAULT_ROOT` environment variable; apply mode raises a clear error when it is unset.

## Validation Commands & Output

### Step-5 unit tests

```
$ pytest tests/test_construction_manifests.py -v
============================== 19 passed in 0.19s ==============================
```

### Targeted regression (new + step-2/3/4 + config/store)

```
$ pytest tests/test_construction_manifests.py tests/test_construction_sources.py \
         tests/test_construction_graph_resolver.py tests/test_construction_graph_delta.py \
         tests/test_construction_store_repositories.py tests/test_config.py \
         tests/test_store.py tests/test_store_links.py -q
80 passed
```

Zero regressions. The 4 pre-existing `test_obsidian_writer` baseline failures from step 4 remain out of scope (untouched here).

### Canonical CLI help subset

```
$ pytest tests/test_cli_canonical.py -k "help_parses or _shape" -q
4 passed
```

Confirms the new `construction-agent sync` command does not break root/auth/run help.

### Ruff

```
$ ruff check src/hb_assistant/construction/ src/hb_assistant/cli/construction.py \
             tests/test_construction_manifests.py
All checks passed!
```

### CLI smoke — dry-run (no live Graph; uses prior step-4 receipts)

```
$ hb-assistant construction-agent sync --dry-run --source-from-receipts-only --json
exit=0
keys: ['command', 'finished_at', 'guardrails', 'manifests', 'mode',
       'processing_receipt', 'rendered', 'run_id', 'skipped', 'started_at',
       'targets', 'written']
mode: dry_run
targets: ['tropical-sharepoint', 'hilltop-sharepoint', 'bobby-onedrive']
source_count: 3
rendered_keys: ['processing_receipt_md', 'source_manifests_md', 'sync_receipts_md']
```

### CLI smoke — apply without env var → structured failure

```
$ hb-assistant construction-agent sync --apply --source-from-receipts-only --json
exit=1
{
  "status": "vault_root_not_configured",
  "error": "Construction vault root not configured. Set the HB_CONSTRUCTION_VAULT_ROOT environment variable to enable apply writes.",
  "hint": "Set HB_CONSTRUCTION_VAULT_ROOT to a writable directory and re-run --apply."
}
```

### CLI smoke — apply with env var → writes to vault subdirectories

```
$ D=$(mktemp -d); HB_CONSTRUCTION_VAULT_ROOT="$D" \
    hb-assistant construction-agent sync --apply --source-from-receipts-only --json
exit=0
mode: apply
written_count: 7
kinds: ['processing_receipt', 'source_manifest', 'sync_receipt']

$D/10_Source_Manifests/bobby-onedrive.manifest.md
$D/10_Source_Manifests/hilltop-sharepoint.manifest.md
$D/10_Source_Manifests/tropical-sharepoint.manifest.md
$D/11_Sync_Receipts/2026-05-27__2a0e4541__bobby-onedrive.sync.md
$D/11_Sync_Receipts/2026-05-27__2a0e4541__hilltop-sharepoint.sync.md
$D/11_Sync_Receipts/2026-05-27__2a0e4541__tropical-sharepoint.sync.md
$D/12_Processing_Receipts/2026-05-27__2a0e4541.processing.md
```

## Rendered Sample Previews (fixture-driven; deterministic)

### Source Manifest (fixture)

```markdown
# Source Manifest — Tropical SharePoint Site

> **Projection only.** SQLite is authoritative. Re-render from store state at any time.

- source_key: `tropical-sharepoint`
- project_key: `tropical`
- kind: `sharepoint_site`
- resolution_status: `resolved`
- drive_id: `b!drive-1`
- web_url: https://contoso.sharepoint.com/sites/Tropical
- generated_at: `2026-05-27T12:00:00+00:00`
- run_id: `fixture-run-001`
- last_sync_at: `2026-05-20T10:00:00+00:00`
- delta_link_fingerprint: `sha256:deadbeefcafe`

## Item Counts

- active: 3
- deleted: 1

## Sample Entries (capped at 20)

| item_id | name | status | size_bytes | is_folder | last_modified |
| --- | --- | --- | --- | --- | --- |
| `i-1` | design.pdf | `active` | 2048 | false | 2026-05-20T10:00:00Z |
| `i-2` | schedule.xlsx | `active` | 51200 | false | 2026-05-21T08:30:00Z |

## Guardrails

- delta_token_storage: `sqlite`
- external_systems: `read_only`
- markdown_role: `projection_only`
- metadata_only: `true`
- sqlite_authoritative: `true`
- writeback: `none`
```

### Sync Receipt (fixture)

```markdown
# Sync Receipt — tropical-sharepoint

> **Projection only.** SQLite is authoritative; this file is a recomputable view.

- run_id: `fixture-run-001`
- mode: `dry_run`
- status: `projected`
- started_at: `2026-05-27T12:00:00+00:00`
- finished_at: `2026-05-27T12:00:01+00:00`

## Counts

- pages_seen: 1
- items_seen: 3
- items_new: 3
- items_updated: 0
- items_deleted: 0
- delta_link_recorded: true

## Error Summary

_no errors_

## Guardrails

- delta_token_storage: `sqlite`
- external_systems: `read_only`
- markdown_role: `projection_only`
- metadata_only: `true`
- sqlite_authoritative: `true`
- writeback: `none`
```

### Processing Receipt (fixture)

```markdown
# Processing Receipt — fixture-run-001

> **Projection only.** SQLite is authoritative; this file is a recomputable view.

- mode: `dry_run`
- started_at: `2026-05-27T12:00:00+00:00`
- finished_at: `2026-05-27T12:00:01+00:00`
- source_count: 1

## Totals

- items_deleted: 0
- items_new: 3
- items_seen: 3
- items_updated: 0
- pages_seen: 1

## Per-Source Status

| source_key | mode | status | pages | items_seen | new | upd | del |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `tropical-sharepoint` | `dry_run` | `projected` | 1 | 3 | 3 | 0 | 0 |

## Error Summary

_no errors_

## Guardrails

- delta_token_storage: `sqlite`
- external_systems: `read_only`
- markdown_role: `projection_only`
- metadata_only: `true`
- sqlite_authoritative: `true`
- writeback: `none`
```

## Guardrails Reaffirmed

- **Markdown role:** projections only. Rendered output is re-derivable from store state. The renderer reads from `ConstructionStore`; it never writes back to SQLite, the source filesystem, or any external system.
- **Delta links remain in SQLite:** the renderer surfaces only `delta_link_fingerprint = sha256:<first-12>` so the raw delta_link (which is a Graph capability token) never appears in vault Markdown. Verified by `test_render_never_leaks_full_delta_link`.
- **No source-document content:** the manifest, sync receipt, and processing receipt schemas exclude `body`, `content`, `text`, `excerpt`, `preview`, `full_text`. Verified by `test_render_never_carries_body_or_text_fields` and the step-4 invariant `test_no_body_or_text_columns_in_inventory`.
- **Apply gate:** apply mode requires the operator to set `HB_CONSTRUCTION_VAULT_ROOT` before any Markdown is written. Dry-run never touches the vault. Verified by `test_apply_requires_env_var` + `test_cli_sync_apply_without_env_var_returns_structured_error`.
- **Marker-bounded writes:** re-runs replace only the bounded block; user text outside the markers is preserved verbatim. Verified by `test_apply_is_marker_bounded_and_preserves_user_text`.
- **Determinism:** the renderer is a pure function over Pydantic models; identical inputs yield byte-identical output. Verified by `test_renderer_is_byte_deterministic`.
- **No live Graph during validation:** dry-run can project from existing SQLite receipts (`--source-from-receipts-only`). Live `--apply` path with a real Graph token is implemented but not exercised here.
- **No new dependencies; no AppConfig changes;** existing `MarkerBoundedWriter` untouched.

## Known Limitations

- Live Graph round-trip not exercised this step (same MSAL sandbox limit documented in step-4 evidence). The orchestrator gracefully falls back to `auth_required` posture or `--source-from-receipts-only` projection.
- All three seeded sources still carry `resolution_status: pending` (step-4 limitation carried forward). The manifest correctly surfaces this; once the SharePoint developer brief is attached and resolutions are persisted, sample-entry tables will populate from real inventory.
- `HB_CONSTRUCTION_VAULT_ROOT` is environment-only for now (not yet a first-class `AppConfig` field). Adding it to `PathsConfig` is a deferred cleanup; today's apply path works correctly with the env var.
- Sample-entry cap defaults to 20 rows per manifest; larger inventories produce a count breakdown via `item_counts` but only a bounded preview. This is intentional (per the prompt's "bounded" intent) and avoids ballooning Markdown.
- Templates use plain `{placeholder}` substitution rather than Jinja. Sufficient for current needs; revisit if conditional rendering or loops grow complex.
- Build-sequence step 3 (full SQLite-schema work) still partial — only the four V2 tables added in step 4 are present.

## Next Prompt

Build-sequence step 6 — Obsidian construction-vault writer (already partially present via `ConstructionVaultWriter` here, but step 6 will broaden to general construction-domain notes, not just receipts).
