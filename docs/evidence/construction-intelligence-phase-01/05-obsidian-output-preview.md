# Phase 01 — Step 6: Obsidian Construction Vault Writer Preview

- Date: 2026-05-27
- Branch: `main`
- HEAD pre-change: `2aa69e6e098ea8dac41ffdea10bff83309217978`
- Prompt: 05 (build-sequence step 6)

## Purpose

Broaden the construction-vault writer with **registry overview**, **project cards**, **review-required notes**, and **policy-gated document cards**; add **folder bootstrap** (dry-run + apply); switch underlying writes to **atomic write-and-replace**; add an **optional config-field fallback** for the vault root; expose everything via `hb-assistant construction-agent vault {bootstrap,preview}`.

SQLite remains authoritative. All Markdown artifacts are recomputable projections, never carry source-document body/text, and are emitted only for the artifact kinds the operator explicitly requests.

## Implementation Summary

| Path | Action |
| --- | --- |
| `src/hb_assistant/config/models.py` | edit (one optional `PathsConfig.construction_vault_root` field) |
| `src/hb_assistant/construction/manifests/models.py` | edit (added `RegistryOverview`, `ProjectCard`, `ReviewRequiredNote`/`ReviewRequiredItem`, `DocumentCard`) |
| `src/hb_assistant/construction/manifests/renderer.py` | edit (added 4 render methods + 4 block helpers) |
| `src/hb_assistant/construction/manifests/service.py` | edit (added 4 builders + `DocumentCardPolicyError` gate) |
| `src/hb_assistant/construction/manifests/vault_writer.py` | edit (4 new subdir kinds + 4 new write methods + `bootstrap_folders` + `_atomic_write_text` + config-fallback root resolution) |
| `src/hb_assistant/construction/manifests/__init__.py` | edit (re-exports for new models + `DocumentCardPolicyError`) |
| `resources/templates/{registry_overview,project_card,review_required,document_card}.template.md` | created |
| `src/hb_assistant/cli/construction.py` | edit (new `vault` Typer group with `bootstrap` and `preview` commands) |
| `tests/test_construction_vault_writer.py` | created (27 tests) |
| `docs/evidence/construction-intelligence-phase-01/05-obsidian-output-preview.md` | created (this file) |

**Untouched:** `MarkerBoundedWriter`, `obsidian/writer.py`, `PathPolicy`, all existing `AppConfig` defaults, all step 0–5 modules. **No new runtime dependencies.**

## Validation Commands & Output

### Step-6 unit tests

```
$ pytest tests/test_construction_vault_writer.py -v
============================== 27 passed in 0.25s ==============================
```

### Targeted regression — new + step-2/3/4/5 + config/store

```
$ pytest tests/test_construction_manifests.py tests/test_construction_sources.py \
         tests/test_construction_graph_resolver.py tests/test_construction_graph_delta.py \
         tests/test_construction_store_repositories.py tests/test_construction_vault_writer.py \
         tests/test_config.py tests/test_store.py tests/test_store_links.py --tb=line -q
107 passed
```

Zero regressions. The 4 pre-existing `test_obsidian_writer` baseline failures from earlier steps remain out of scope (untouched here).

### Canonical CLI help subset

```
$ pytest tests/test_cli_canonical.py -k "help_parses or _shape" -q
4 passed
```

Confirms the new `vault` subcommand group does not break root/auth/run help parsing.

### Ruff

```
$ ruff check src/hb_assistant/construction/ src/hb_assistant/config/models.py \
             src/hb_assistant/cli/construction.py tests/test_construction_vault_writer.py
All checks passed!
```

### CLI smoke

**`vault bootstrap --dry-run --json` (no env var):**

```json
{
  "command": "construction-agent vault bootstrap",
  "mode": "dry_run",
  "status": "vault_root_not_configured",
  "planned_subdirs": [
    "00_Registry", "01_Projects", "02_Review_Queue", "03_Document_Cards",
    "10_Source_Manifests", "11_Sync_Receipts", "12_Processing_Receipts"
  ],
  "hint": "Set HB_CONSTRUCTION_VAULT_ROOT or AppConfig.paths.construction_vault_root to enable apply writes."
}
```

Exit 0. The planned 7 subdirs are surfaced even without a configured root, so operators can preview the structure before opting in.

**`HB_CONSTRUCTION_VAULT_ROOT=$D vault bootstrap --apply --json`:**

```text
Exit 0. All 7 subdirs created under $D:
$D/00_Registry/
$D/01_Projects/
$D/02_Review_Queue/
$D/03_Document_Cards/
$D/10_Source_Manifests/
$D/11_Sync_Receipts/
$D/12_Processing_Receipts/
```

**`HB_CONSTRUCTION_VAULT_ROOT=$D vault preview --apply --json` (default flags):**

```text
exit=0
mode: apply
written kinds: ['project_card', 'registry_overview', 'review_required']

$D/00_Registry/registry-overview.md
$D/01_Projects/hilltop.project.md
$D/01_Projects/tropical.project.md
$D/02_Review_Queue/2026-05-27__review-required.md
```

No files under `03_Document_Cards/` — confirms the opt-in-only policy.

**`vault preview --include-document-cards --json` without `--document-item` / `--policy-reason`:**

```json
{
  "status": "document_card_requires_item_and_policy",
  "hint": "Pass --document-item ITEM_ID --policy-reason REASON when using --include-document-cards."
}
```

Exit 1. Structured rejection rather than silent emission.

## Rendered Fixture Previews (deterministic)

### Registry Overview

```markdown
---
type: construction-registry-overview
domain: construction
status: active
tags: [construction, registry, overview]
owner: Bobby Fetting
generated: 2026-05-27T12:00:00+00:00
---

# Construction Registry Overview

> **Projection only.** SQLite is authoritative. Re-render from store state at any time.

- generated_at: `2026-05-27T12:00:00+00:00`
- project_count: 2
- source_count: 3

## Projects

| project_key | display_name | status | primary_company |
| --- | --- | --- | --- |
| `tropical` | Tropical | `active` | HB Construction |
| `hilltop` | Hilltop | `active` | HB Construction |

## Sources by Project

- **_unassigned_**: `bobby-onedrive`
- **hilltop**: `hilltop-sharepoint`
- **tropical**: `tropical-sharepoint`

## Unresolved Sources

- `bobby-onedrive`
- `hilltop-sharepoint`

## Guardrails

- delta_token_storage: `sqlite`
- external_systems: `read_only`
- markdown_role: `projection_only`
- metadata_only: `true`
- sqlite_authoritative: `true`
- writeback: `none`
```

### Project Card (Tropical)

```markdown
---
type: construction-project-card
domain: construction
status: active
tags: [construction, project, "tropical"]
owner: Bobby Fetting
generated: 2026-05-27T12:00:00+00:00
project_key: tropical
---

# Project — Tropical

> **Projection only.** SQLite is authoritative; this card is a recomputable view.

- project_key: `tropical`
- display_name: Tropical
- status: `active`
- primary_company: HB Construction
- source_count: 1
- last_sync_at: `2026-05-20T10:00:00+00:00`
- generated_at: `2026-05-27T12:00:00+00:00`

## Registered Sources

- `tropical-sharepoint`

## Totals (across all project sources)

- active: 3

## Guardrails

- delta_token_storage: `sqlite`
- external_systems: `read_only`
- markdown_role: `projection_only`
- metadata_only: `true`
- sqlite_authoritative: `true`
- writeback: `none`
```

### Review-Required Note (empty state — pre-step-7)

```markdown
---
type: construction-review-required
domain: construction
status: active
tags: [construction, review, queue]
owner: Bobby Fetting
generated: 2026-05-27T12:00:00+00:00
---

# Review Required

> **Projection only.** SQLite is authoritative.
> Items appear here when classification or policy routes them to manual review.

- generated_at: `2026-05-27T12:00:00+00:00`
- item_count: 0

## Items

_no items currently flagged for review_

## Guardrails

- delta_token_storage: `sqlite`
- external_systems: `read_only`
- markdown_role: `projection_only`
- metadata_only: `true`
- sqlite_authoritative: `true`
- writeback: `none`
```

### Document Card (opt-in only; fixture)

```markdown
---
type: construction-document-card
domain: construction
status: active
tags: [construction, document-card, "tropical-sharepoint"]
owner: Bobby Fetting
generated: 2026-05-27T12:00:00+00:00
source_key: tropical-sharepoint
item_id: item-1
policy_reason: manual review requested by operator
---

# Document Card — design.pdf

> **Projection only.** No source-document content is stored; metadata only.
> This card was emitted because policy explicitly permitted it.

- source_key: `tropical-sharepoint`
- project_key: `tropical`
- item_id: `item-1`
- name: design.pdf
- web_url: https://x/item-1
- parent_path: `/drives/b!drive-1/root:/Project`
- size_bytes: 2048
- is_folder: false
- last_modified: `2026-05-20T10:00:00Z`
- status: `active`
- policy_reason: `manual review requested by operator`
- generated_at: `2026-05-27T12:00:00+00:00`

## Guardrails

- delta_token_storage: `sqlite`
- external_systems: `read_only`
- markdown_role: `projection_only`
- metadata_only: `true`
- sqlite_authoritative: `true`
- writeback: `none`
```

## Guardrails Reaffirmed

- **No source-document content:** all 4 new render kinds exclude `body:`, `content:`, `text:`, `excerpt:`, `full_text:`. Verified by parametrized `test_render_never_carries_body_or_text_fields` (4 cases).
- **No auto document cards:** the service raises `DocumentCardPolicyError` when asked to emit a card without a non-empty `policy_reason`; the CLI requires `--include-document-cards`, `--document-item`, `--policy-reason`, AND `--source` together. Verified by `test_document_card_requires_non_empty_policy_reason` + `test_cli_vault_preview_document_card_requires_flags`. Apply runs without these flags create zero files under `03_Document_Cards/`.
- **Atomic writes:** all writes go through `_atomic_write_text` (temp file in same dir → `os.replace`). Failure mid-write leaves the original file unchanged and removes the temp file. Verified by `test_atomic_write_failure_preserves_existing_file`.
- **Marker-bounded re-runs:** each kind has its own bounded markers (`HB-CONSTRUCTION-REGISTRY`, `HB-CONSTRUCTION-PROJECT-CARD`, `HB-CONSTRUCTION-REVIEW`, `HB-CONSTRUCTION-DOC-CARD`). User text outside the markers is preserved verbatim. Verified by `test_registry_overview_marker_bounded_preserves_user_text` + `test_project_card_marker_bounded`.
- **Apply gate:** apply requires the construction-vault root resolved from ctor arg → env var → `AppConfig.paths.construction_vault_root`. When none set, structured `vault_root_not_configured` error (exit 1). Verified by `test_unset_raises_on_apply` + `test_cli_vault_preview_apply_without_env_returns_structured_error`.
- **Frontmatter validity:** YAML frontmatter parses cleanly with required keys (`type`, `domain: construction`, `tags`, `owner`, `generated`). Verified by `test_registry_overview_frontmatter_is_valid` + `test_project_card_frontmatter_is_valid`.
- **Determinism:** the renderer remains a pure function over Pydantic models; fixture-driven evidence is byte-reproducible across runs.
- **SQLite still authoritative:** the new vault writer reads from `ConstructionStore` and the registry but never mutates the store.

## Known Limitations

- Live Graph round-trip not exercised this step (same MSAL sandbox limit documented in step 4/5 evidence). Bootstrap + preview work fully without it.
- The review-required note currently renders the empty-state placeholder until step 7 wires the actual classification/queue source. The renderer + writer are forward-compatible — only the CLI's item supplier needs to change.
- All three seeded sources still carry `resolution_status: pending`, so the registry overview correctly lists `bobby-onedrive` and `hilltop-sharepoint` under unresolved.
- `HB_CONSTRUCTION_VAULT_ROOT` env var has higher precedence than the new `AppConfig.paths.construction_vault_root` config field. Either works; the env var keeps operational ergonomics for ad-hoc / sandbox runs.
- Sample-entry caps from step 5 still apply to source manifests (default 20).
- `resources/checklists/obsidian_output_validation_checklist.md` referenced by the prompt does not exist in repo; not fabricated.
- The `_unassigned_` bucket appears in registry overview "Sources by Project" only when a registered source has `project_key: null` (currently `bobby-onedrive`); this is intentional surfacing of orphan sources for review.

## Next Prompt

Build-sequence step 7 — Review queue and sensitive data routing — will populate the review-required note with real items (classification engine + sensitivity routing). The renderer/writer added here will accept that supplier without further code changes.
