# Phase 02 — Prompt 01 — Source Registry Reality Alignment

## 1. Summary

Phase 01 shipped a minimal placeholder source registry (2 projects, 3 sources, all `resolution_status: pending`, narrow field set). This prompt expands the model and seed to the **Phase 02 canonical reality**:

- **Models** (`src/hb_assistant/construction/config/models.py`) gain four typed sub-models — `DefaultPolicies`, `BaselinePolicy`, `BaselineSnapshot`, `FolderPolicies` — plus ~14 new optional fields on `SourceLocation` and 4 new optional fields on `ProjectIdentity`. The `SourceKind` and `ResolutionStatus` literals are extended with the Phase 02 scopes/statuses. A new `SourceSystem` literal is added.
- **Compatibility bridge**: Pydantic `validation_alias=AliasChoices(...)` lets YAML supply either Phase 01 names (`source_key`, `kind`, `display_name`, `root_path`) or Phase 02 canonical names (`source_id`, `source_scope`, `source_name`, `folder_path`). Internal Python field names stay on Phase 01 spelling so downstream code (graph resolver, manifests, vault writer, classifier, CLI, fixtures) is untouched. A `model_validator(mode="before")` raises if both alias spellings are supplied with **conflicting** values (stop-condition guard); identical-value duplicates are silently collapsed.
- **Hard guardrails** baked into model validators:
  - `DefaultPolicies.read_only` cannot be False;
  - `DefaultPolicies.copy_originals_to_vault` cannot be True;
  - `DefaultPolicies.store_full_text_in_vault_notes` cannot be True;
  - `FolderPolicies` rejects any folder name appearing in both `review_required` and `deep_index_allowed`.
- **Seed** (`resources/config/sharepoint_onedrive_sources.seed.yaml`) is additively expanded from 2 projects / 3 sources to **6 projects / 14 sources**. The 3 Phase 01 records (`tropical-sharepoint`, `hilltop-sharepoint`, `bobby-onedrive`) are retained verbatim; 11 canonical Phase 02 records are appended. The `tropical` project record is enriched in-place with `project_number`, `procore_project_id`, `project_name_normalized` (display_name unchanged). A new `default_policies` block exercises `DefaultPolicies` and locks the registry-level guardrails.
- **Schema** (`resources/schemas/source_locations.schema.json`) is regenerated from the model via `SourceLocation.model_json_schema()` — now 566 lines with nested `$defs` for the four sub-models.
- **Tests** (`tests/test_construction_sources.py`) grow from 14 to 42 (+28 net). One vault-writer test (`test_project_card_aggregates_totals`) updated to reflect that `tropical` now owns two sources (legacy + canonical).

No SQLite migration, no CLI surface change, no downstream code migration. Compatibility aliases come out only after every downstream reference is migrated — see §10 (Compatibility Bridge TODO).

## 2. Repo HEAD — Before / After

| Marker | Value |
| --- | --- |
| Branch | `main` |
| HEAD before | `cd9f014b296a761a8965d14545c55c6d38933c06` ("docs(construction-agent): create phase 02 evidence root with preflight rebaseline") |
| HEAD after  | (to be recorded after commit) |
| Working tree before | clean |

## 3. Files Changed

**Modified (6):**

- `src/hb_assistant/construction/config/models.py` — extended literals, added 4 typed sub-models, added validation aliases on `SourceLocation` and `ProjectIdentity`, added conflict + folder-policy + default-policy validators, added `folder_item_id` uniqueness validator on `SourceRegistry`, relaxed `drive_id` validator to allow legitimate folder-level reuse within the same drive.
- `src/hb_assistant/construction/config/__init__.py` — export the new sub-models and literals.
- `resources/config/sharepoint_onedrive_sources.seed.yaml` — replaced 3 sources / 2 projects with 14 sources / 6 projects (Phase 01 records preserved verbatim, Phase 02 canonical records appended, top-level `default_policies` block added).
- `resources/schemas/source_locations.schema.json` — regenerated from `SourceLocation.model_json_schema()`.
- `tests/test_construction_sources.py` — 14 → 42 tests. Existing assertions updated for new counts; new tests cover legacy/canonical/mixed YAML loading, alias-conflict detection, identical-alias collapse, source_id uniqueness, underscore identifier acceptance, new source scopes + resolution statuses, baseline/folder-policy parsing, hard-guardrail rejections, default-policy safe defaults, folder_item_id uniqueness, drive_id reuse permission.
- `tests/test_construction_vault_writer.py` — single-line fix in `test_project_card_aggregates_totals` (source_count 1 → 2 for tropical; added assertion that both legacy and canonical source_keys are present).

**Created (1):**

- `docs/evidence/construction-intelligence-phase-02/01-source-registry-reality-alignment.md` — this file.

**Deleted:** none. **Migrations applied:** none (SQLite schema_version stays at 4).

## 4. Governance Attestation

| Reference | Status |
| --- | --- |
| `CLAUDE.md` §5 — "Obsidian Vault Planning and Implementation Package Governance" | Read and honored. Implementation-package payload at `~/Downloads/HB_Construction_Intelligence_Phase_02_Implementation_Package/` consulted as guidance only; no payload copied under `docs/plans/**`. |
| `.grok/skills/vault-package-governance/SKILL.md` | Honored. |
| Phase 01 evidence (`session-handoff.md`, `11-final-closeout-summary.md`) | Carried forward as authoritative context. |
| Phase 02 package files (Prompt_01 spec, canonical_source_registry.phase02.seed.yaml, source_registry_field_mapping.yaml, source_locations.canonical.schema.json) | Read; canonical seed values mirrored into the repo seed. Top-level `version`, `registry_status`, `repo_root`, `vault_roots`, `sqlite_path` keys deliberately omitted from the repo seed (out of scope for SourceRegistry model). |

## 5. Validation Commands and Outputs

All commands executed from `/Users/bobbyfetting/hb-personal-assistant`. Date: 2026-05-27.

### 5.1 `python -m pytest tests/test_construction_*.py tests/test_procore_*.py`

```text
........................................................................ [ 26%]
........................................................................ [ 53%]
........................................................................ [ 80%]
....................................................                     [100%]
268 passed in 3.86s
```

268 = 240 prior + 28 new (all in `tests/test_construction_sources.py`). Zero failures.

### 5.2 `ruff check src/hb_assistant/construction/ src/hb_assistant/procore/ src/hb_assistant/cli/construction.py src/hb_assistant/cli/procore.py`

```text
All checks passed!
```

### 5.3 `hb-assistant construction-agent validate --json`

```json
{
  "command": "construction-agent validate",
  "checks": [
    {"name": "schema",          "ok": true, "detail": "schema_version=4"},
    {"name": "source_registry", "ok": true, "detail": "6 projects, 14 sources"},
    {"name": "review_rules",    "ok": true, "detail": "version=1; 12 rules; threshold=0.7"},
    {"name": "model_routing",   "ok": true, "detail": "version=1; default_model=llama3.2:1b; tasks=['classification', 'review_reason']"}
  ],
  "summary": {"total": 4, "passed": 4, "failed": 0, "ok": true},
  "guardrails": {"external_systems": "read_only", "writeback": "none", "metadata_only": true, "command_role": "read_only_dashboard"}
}
```

### 5.4 `hb-assistant construction-agent sources validate --json` (summary)

```json
{
  "implemented": true,
  "phase": 1,
  "step": "2-source-registry",
  "summary": {
    "project_count": 6,
    "source_count": 14,
    "resolved_count": 0,
    "pending_count": 9,
    "deprecated_count": 0,
    "ok": true,
    "blocking": false
  },
  "guardrails": {"all_read_only": true, "no_writeback_paths": true, "no_live_external_calls": true},
  "note": "Read-only validation. No SharePoint/OneDrive/Graph calls were made."
}
```

The CLI's `pending_count: 9` only tallies records with `resolution_status == "pending"` (the 3 legacy + 6 canonical with default status). The remaining 5 records use the new Phase 02 statuses (1 `graph_delta_ready`, 1 `pending_graph_resolution`, 2 `pending_drive_resolution`, 1 `pending_source_resolution`) — these are visible in `sources validate` per-row output but not yet counted in the legacy summary buckets. Counter migration is logged in §10.

### 5.5 `hb-assistant construction-agent index status --json` (head)

```json
{
  "command": "construction-agent index status",
  "schema_version": 4,
  "summary": {"project_count": 6, "source_count": 14, "sources_in_view": 14},
  "review_queue": {"open": 0, "resolved": 0, "deferred": 0},
  "model_decisions": {"accepted": 1, "review": 2},
  "policies": {
    "review_rules":  {"version": 1, "rule_count": 12, "low_confidence_threshold": 0.7},
    "model_routing": {"version": 1, "default_model": "llama3.2:1b", "low_confidence_threshold": 0.7, "tasks": ["classification", "review_reason"]}
  }
}
```

Per-source rows include the 3 legacy entries (Phase 01 shape) and the 11 canonical entries (Phase 02 shape) — all surfaced through the Phase 01 internal field names. Full transcript truncated for brevity.

### 5.6 `hb-assistant procore mapping validate --json` (exit 1 by design)

```json
{
  "command": "hb-assistant procore mapping validate",
  "report": {
    "company_id": "5280",
    "total": 2,
    "by_status": {"pilot": 1, "pending": 1},
    "rows": [
      {"hb_project_key": "tropical", "procore_project_id": "23-435-01", "procore_project_name": "Tropical", "status": "pilot",   "mapped": true},
      {"hb_project_key": "hilltop",  "procore_project_id": "",          "procore_project_name": "",         "status": "pending", "mapped": false}
    ],
    "ok": false
  }
}
```

`procore_projects.seed.yaml` is a separate registry and is intentionally out of scope this prompt. The canonical `procore_project_id` values now carried on `ProjectIdentity` (e.g. tropical → 2525840) reflect the Phase 02 corrected mapping called out in the package — the Procore audit surface migration to use them is a later Phase 02 prompt.

### 5.7 `hb-assistant construction-agent graph auth status --json` (excerpt)

```json
{
  "command": "construction-agent graph auth status",
  "delegated": {"token_type": "none", "message": "No delegated token. Run login."},
  "note": "No live Graph call is made; report is from local MSAL cache only."
}
```

### 5.8 `hb-assistant construction-agent graph sources resolve --json`

```json
{
  "command": "construction-agent graph sources resolve",
  "mode": "dry_run",
  "targets": [
    "tropical-sharepoint", "hilltop-sharepoint", "bobby-onedrive",
    "sp_2023projects_23_435_01_tropical_sl",
    "sp_2025projects_25_264_01_atlantic_fields_club_core",
    "sp_2022projects_22_112_01_pga_the_modern_garage",
    "sp_2024projects_24_606_01_alton_hilltop_pbg",
    "sp_2025projects_25_244_01_the_wellington",
    "sp_2026projects_26_727_01_wellington_marketplace_condo_hotel",
    "sp_2026projects_26_898_01_wellington_townhomes",
    "sp_hilltop_gardens_projecthome",
    "od_business_bobby_hedrickbrothers",
    "od_personal_bobby",
    "od_shared_libraries_cloudtemp"
  ],
  "status": "auth_required",
  "detail": "No delegated account in cache. Run `hb-assistant auth login` first."
}
```

All 14 source keys (3 legacy + 11 canonical) surface cleanly in the resolver's target list. Exit 0; no MSAL hang.

## 6. Guardrail Attestation (Phase 02 specific)

- External systems remain read-only — no SharePoint, OneDrive, Outlook, or Procore writeback. `SourceLocation.read_only` is still `Literal[True]`.
- `DefaultPolicies.copy_originals_to_vault` rejected when True (model-level): no source-document copies into Obsidian by default.
- `DefaultPolicies.store_full_text_in_vault_notes` rejected when True (model-level): no full-document text in vault notes by default.
- `FolderPolicies` rejects folders appearing in both `review_required` and `deep_index_allowed`: no silent deep-indexing of review-required folders.
- No deletion/movement/overwrite/rename of source files.
- No production webhooks introduced.
- No company-wide rollout.
- Sensitive records route to review (the canonical Tropical source's `folder_policies.review_required` lists Est, Accounting, ChangeOrder, Monthly Forecast, contracts, change orders, financial reports).
- Models execute no file operations and have no path to override controller validation.
- `Mail.ReadWrite.All` still enforces read-only mailbox behavior (Outlook source_system is declared in the literal but no mailbox source exists in the seed and no email surface lands this prompt).
- Stop conditions honored: no ambiguous duplicate identity emerged from the alias bridge (conflict-detection validator raises clean errors).

## 7. Blocked Live / External Validation

- **Graph** — `graph auth status` and `graph sources resolve --json` return structured `auth_required` payloads without contacting Microsoft. MSAL token cache is empty in this non-interactive shell. Live resolution will be exercised in a later prompt once an interactive `hb-assistant auth login` populates the cache.
- **Procore** — `mapping validate` runs against the separate `procore_projects.seed.yaml` (still showing hilltop pending); no live Procore call is possible (OAuth still stubbed).
- **Ollama** — not touched this prompt.

## 8. Phase 02 Acceptance Progress

Status of the Phase 01 acceptance gaps catalogued in Phase 02 Prompt 00 §6:

| Gap | Status after this prompt |
| --- | --- |
| 1. Live MS Graph round-trip | Still deferred (requires interactive shell). |
| 2. SharePoint/OneDrive seeds `resolution_status: pending` with null IDs | **Partially closed.** sp_2023projects_23_435_01_tropical_sl now has full canonical IDs (site_id, drive_id, folder_item_id, list_id) and status `graph_delta_ready`. 10 other canonical sources carry resolved drive_id/folder_item_id values with pending statuses awaiting live resolution. Legacy compat records remain pending. |
| 3. Live Ollama CLI gate | Untouched. |
| 4. Procore OAuth stub | Untouched. `procore_project_id` now carried on `ProjectIdentity` for 4 projects (tropical, pga-modern-garage, alton-hilltop-pbg, the-wellington), unblocking later Procore mapping migration. |
| 5. Procore mapping incomplete (hilltop) | Untouched in `procore_projects.seed.yaml`. |
| 6. `paths.construction_vault_root` unset in `config/config.yml` | Untouched. |
| 7. Pre-existing `test_obsidian_writer.py` failures | Untouched (out of scope). |
| 8. Hang-prone test files | Untouched (out of scope). |

## 9. Test Detail

`tests/test_construction_sources.py` final count = 42 (was 14). New tests by area:

- **Seed shape** (4): updated `test_seed_loads_with_expected_projects_and_sources`; new `test_seed_sources_are_all_read_only`, `test_seed_resolution_statuses_are_in_allowed_set`, `test_seed_legacy_compat_sources_have_no_fabricated_ids`, `test_seed_default_policies_enforce_safe_defaults`.
- **Compatibility bridge** (8): `test_legacy_phase1_yaml_shape_still_loads`, `test_canonical_phase2_yaml_shape_loads`, `test_mixed_legacy_and_canonical_seed_loads`, `test_conflicting_source_alias_pair_raises`, `test_conflicting_kind_alias_pair_raises`, `test_conflicting_project_name_alias_pair_raises`, `test_identical_alias_pair_is_accepted`, `test_canonical_source_ids_are_unique_in_registry`, `test_underscore_canonical_source_id_accepted`.
- **New literals** (3): `test_new_source_scopes_accepted`, `test_new_resolution_statuses_accepted`, `test_source_kind_literal_contains_phase01_and_phase02_values`.
- **Backwards-compat** (1): `test_legacy_sources_can_omit_phase02_fields`.
- **Uniqueness** (2): `test_duplicate_folder_item_id_rejected`, `test_drive_id_reuse_is_allowed`.
- **Typed policies** (10): `test_canonical_baseline_policy_loads`, `test_canonical_baseline_snapshot_loads`, `test_canonical_folder_policies_load`, `test_invalid_baseline_mode_fails`, `test_invalid_indexing_depth_fails`, `test_folder_policy_review_required_cannot_be_deep_indexed`, `test_default_policies_rejects_copy_originals_true`, `test_default_policies_rejects_full_text_in_vault_notes_true`, `test_default_policies_rejects_read_only_false`, `test_default_policies_safe_defaults_when_empty`.

## 10. Compatibility Bridge TODO (carry into later Phase 02 prompts)

The Phase 02 compatibility aliases (`source_id`↔`source_key`, `source_scope`↔`kind`, `source_name`↔`display_name`, `folder_path`↔`root_path`) must remain in place until **every** downstream reference is migrated to canonical names. The compatibility-removal prompt is gated on the following surfaces converting first:

- `src/hb_assistant/construction/graph/resolver.py` and `graph/delta_crawler.py` — both reference `source_key`, `kind`, `display_name`.
- `src/hb_assistant/construction/manifests/{service,renderer,vault_writer}.py` — source-key plumbing throughout; manifest templates use the legacy field names.
- `src/hb_assistant/construction/policy/{evaluator,router}.py` and `construction/classification/router.py` — use `source_key` as the routing key.
- `src/hb_assistant/cli/construction.py` — `sources list`, `index status`, `graph delta` output and arg parsing keyed on `source_key`. CLI summary buckets (`pending_count`, `resolved_count`) need to learn the new Phase 02 statuses (`graph_delta_ready`, `pending_*`).
- `src/hb_assistant/construction/fixtures/*` — synthetic data uses legacy field names.
- `tests/test_construction_*.py` (excluding sources) — hardcoded `tropical-sharepoint`, `hilltop-sharepoint`, `bobby-onedrive` literals.
- SQLite store tables — Phase 02 may add columns for `tenant_id`, `folder_item_id`, `folder_web_url`, `list_id`, `baseline_*` metadata once the resolved canonical sources land in `construction_source_inventory`.

When all of the above are converted, a future prompt can: (a) rename the Python field names to canonical, (b) drop the aliases, (c) deprecate or remove the legacy compat records in the seed.

## 11. Next Prompt Readiness

- Repo at expected baseline (HEAD `cd9f014`).
- Working tree changes captured in §3.
- 268/268 scoped tests pass; ruff clean.
- All Phase 02 hard guardrails enforced at model level.
- Compatibility bridge live; canonical seed loaded without downstream breakage.
- TODO catalogue (§10) carries the next-prompt migration map.

**Status: ready for Phase 02 — Prompt 02.**
