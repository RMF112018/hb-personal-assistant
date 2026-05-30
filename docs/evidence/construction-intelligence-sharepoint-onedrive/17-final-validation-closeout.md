# 17 — Final Validation & Phase Closeout (Phase 06A)

**Prompt:** Prompt 17 — Final Closeout and Evidence Package · **Date:** 2026-05-30
**Posture:** Read-only delegated Graph; offline-deterministic for SQLite/retrieval/proof commands;
the only live calls are read-only GET probes; no Microsoft 365 writeback; **schema V19 is final for
this phase** (no migration in Prompts 16–17). **Status: Closed (Prompts 00–17).**

## 1. SHAs

| Marker | SHA | Note |
|---|---|---|
| Pre-phase baseline | `0586885` | phase-06 email-track closeout (parent of Phase 06A) |
| Phase 06A first commit | `8c844bd` | prompt-00: repo-truth rebaseline + graph files readiness audit |
| Last functional commit | `c40f53b` | prompt-16: end-to-end pilot & no-writeback/no-secret proof |
| Closeout | this commit | prompt-17: final validation closeout (docs only) |

## 2. Files changed (`0586885..c40f53b`) — 80 files, +12634 / −113

- **Endpoint guard:** `src/hb_assistant/graph/files_endpoint_guard.py` (+ 4 endpoint YAML configs:
  `graph_files_read_endpoint_allowlist.yaml`, `graph_files_mutation_endpoint_blocklist.yaml`,
  `graph_files_drive_item_metadata_field_contract.yaml`, `file_ingestion_policy.seed.yaml`).
- **12 graph modules** under `src/hb_assistant/construction/graph/`: `link_resolver`,
  `site_drive_discovery`, `drive_item_indexer`, `baseline_crawler`, `delta_sync`,
  `file_project_matcher`, `ingestion_eligibility`, `controlled_extraction`, `file_review_router`,
  `file_obsidian_projection`, `file_retrieval` (+ `construction/policy/file_ingestion.py`).
- **Plumbing:** `cli/graph.py` (the `graph files` command surface), `construction/source_projection.py`,
  `construction/drive_item_bridge.py`, `construction/store/repositories.py`, `store/migrator.py`
  (additive **V15–V19**), `review_required_rules.seed.yaml` (16→25 rules).
- **16 new** `tests/test_graph_files_*.py` (+ touched `test_mutation_lockout.py`,
  `test_source_registry_projection.py`, and prior-track schema tests).
- **Docs:** `resources/json/phase_06a_files_validation_matrix.json`,
  `docs/architecture/18-sharepoint-onedrive-file-intelligence-phase-06.md`,
  `docs/runbooks/phase-06a-operational-sharepoint-onedrive-workflows.md`, and **24** evidence files
  `00`…`22`, `16`, `17` under `docs/evidence/construction-intelligence-sharepoint-onedrive/`.

(Full `git diff --name-status` archived in commit history; counts are the canonical inventory.)

## 3. Full validation matrix readout (`resources/json/phase_06a_files_validation_matrix.json`)

| # | Command | Captured result |
|---|---------|-----------------|
| 1 | `python -m pytest -q --no-header` | **12 failed, 1698 passed, 2 skipped** — the 12 are the pre-existing email-track baseline (see §6); **0 Phase 06A files failures** |
| 2 | `ruff check .` | All checks passed |
| 3 | `mypy src` | Success: no issues found in **142** source files |
| 4 | `python -m compileall src tests` | exit 0 |
| 5 | `diagnostics graph --safe --json` | live read-only `/me` probe `200` (UPN only; no body) |
| 6 | `auth status --json` | `mode=delegated`, valid token (`expires_in≈2809s`), scope NAMES only |
| 7 | `construction-agent validate --json` | **4/4** (`schema_version=19`) |
| 8 | `graph files status --json` | `ok` (registry 14, review-queue open 0) |
| 9 | `graph files sources --json` | `ok` (dry_run; 14 sources) |
| 10 | `graph files sites --dry-run --json` | `auth_required` (dry_run; no live call) |
| 11 | `graph files drives … --dry-run --json` | `auth_required` |
| 12 | `graph files onedrive … --dry-run --json` | `auth_required` |
| 13 | `graph files crawl … --dry-run --json` | `auth_required` |
| 14 | `graph files delta … --dry-run --json` | `auth_required` |
| 15 | `graph files project-match --project tropical --dry-run --json` | `ok` (dry_run; `graph_calls=none`) |
| 16 | `graph files ingestion-policy … --dry-run --json` | `ok` (dry_run; `block_review_required_extraction=true`) |
| 17 | `graph files obsidian … --dry-run --json` | `ok` (dry_run; `source_file_copied_to_vault=false`) |
| 18 | `graph files retrieve --project tropical --query "RFI submittal meeting minutes" --json` | `ok` (`full_text_persisted=false`, `review_routed_excluded=true`) |
| 19 | `graph files no-writeback-proof --json` | `ok` — guard self-test passed (24 GET allowed / **19 mutation blocked** / 0 anomalies); static scan **0** mutating calls across **39** files |

**Additional validation — `user_provided_link_resolution`:** `tests/test_graph_files_link_resolver.py`
**16 passed**, covering the matrix's 7 `required_tests` (`encode_sharing_url_unpadded_base64url`,
`resolve_shares_driveItem_folder/_file`, `business_onedrive_root_fallback`,
`malformed_url_no_graph_call`, `no_redeemSharingLink_by_default`,
`no_raw_url_or_share_token_persistence`); evidence `05a-user-provided-link-resolution-proof.json` present.

## 4. Operational capabilities (read-only, dry-run-default `hb-assistant graph files`)

`status` → `sources` (canonical V5 projection) → SharePoint `sites`/`site resolve`/`drives` +
`onedrive` discovery → user-provided `link resolve` (read-only Shares API; no redemption) →
`index`/`crawl`/`delta` (metadata-only; delta links surface only as SHA-256 fingerprints) →
`project-match` → `ingestion-policy` → controlled `extract` (explicit `--download`/`--extract`;
bounded redacted; cache deleted after parse) → `review-queue` (sensitive routing; idempotent) →
`obsidian` (grouped marker-bounded manifests/registers/review-summaries/receipts; no file copy) →
`retrieve` (source-linked over bounded redacted excerpts; review-routed excluded) →
`no-writeback-proof`. Additive schema **V15–V19** with `full_text_persisted=0` /
`source_file_copied_to_vault=0` / `raw_download_url_persisted=0` / `review_required → no extraction`
CHECKs. Read-only at four layers (source policy, SQLite CHECK, files endpoint guard,
`microsoft_365_writeback_enabled == False`).

## 5. Deferred permission tightening

Broad `Files.ReadWrite.All` (and tenant-consented `Sites.*`/`AllSites.FullControl`) consent is
**retained and intentionally not tightened in this phase** — a documented risk recorded in
`22-deferred-permission-tightening-record.md` and `02-graph-auth-permission-posture-deferred.md`. The
runtime requests minimized scopes and stays behaviorally read-only at four layers; the
`no-writeback-proof` surfaces the broad scopes and marks `permission_tightening: deferred`.
Remediation (scope reduction / re-consent) is handed forward as a separate hardening task.

## 6. Remaining limitations

- **Graph-discovery offline degradation:** `sites`/`drives`/`onedrive`/`crawl`/`delta` return
  `auth_required` (exit 0, no live call) without a files-scoped delegated token; live verification is
  a future operational step, not a code gap.
- **Shared-library resolution** limits are documented in `18-shared-library-resolution-limitations.md`.
- **12 pre-existing email-track test failures** (`'ConstructionStore' object has no attribute
  'upsert_email_model_classification'`) in `test_automation.py` (4), `test_email_classifier.py` (7),
  `test_email_model_classifications_schema_v14.py` (1). These belong to the **email** intelligence
  track (`construction/email/email_classifier.py`), predate Phase 06A, were not touched by any
  SharePoint/OneDrive files module, and are **out of scope** for this closeout. They are **not fixed
  here** (surgical-changes rule) and do **not** block the files-track closeout; they are handed to the
  email track for resolution. No new failure was introduced by Phase 06A — all 16 `test_graph_files_*`
  suites pass.

## 7. Guardrails honored

```json
{
  "microsoft_365_writeback": "none",
  "file_mutation_endpoints_blocked": true,
  "no_mutation_method_calls_in_file_services": true,
  "source_file_copied_to_vault": false,
  "full_text_persisted": false,
  "raw_download_url_persisted": false,
  "raw_delta_links_rendered": false,
  "review_routed_excluded": true,
  "dry_run_default": true,
  "no_matched_secret_values_emitted": true,
  "schema_version": 19,
  "permission_tightening": "deferred"
}
```

**Closeout:** Phase 06A — SharePoint / OneDrive File Intelligence — **Closed (Prompts 00–17)**, schema
final at V19, files track fully validated, broad file-permission tightening deferred (documented).
