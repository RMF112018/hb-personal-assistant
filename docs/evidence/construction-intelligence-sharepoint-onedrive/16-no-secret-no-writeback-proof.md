# 16 — End-to-End Pilot, No-Secret & No-Writeback Proof (Phase 06A)

**Prompt:** Prompt 16 — End-to-End Pilot Validation and No-Writeback Proof · **Date:** 2026-05-30
**Posture:** Read-only delegated Graph; offline-deterministic for SQLite/retrieval/proof commands;
the only live calls are read-only GET probes (`diagnostics graph --safe` → `/me`); no Microsoft 365
writeback; **no new migration** (schema stays at version 19).

## What this proves

An end-to-end pilot over the already-built `hb-assistant graph files` surface (Prompts 02–15),
exercising the Phase 06A validation matrix and producing behavior-level proof that the runtime:
makes **no Microsoft 365 writeback**, persists **no secret/token/signed-URL/raw-delta-link**, and
copies **no source file into Obsidian**. No code or schema was changed in this prompt; the only repo
artifact added is the validation matrix itself.

- Added `resources/json/phase_06a_files_validation_matrix.json` (verbatim from the phase package) so
  the matrix Prompt 17 gates on, and that this pilot runs, lives at the referenced path.

## Pilot matrix readout

Run inside `.venv`. `--json` on every command; offline commands return `ok: true`; the five
Graph-discovery dry-runs degrade to `auth_required` (exit 0, no live call, no writeback) because the
cached token does not carry the files-discovery delegated scopes — the documented deferred-to-live
posture.

| # | Command | Result |
|---|---------|--------|
| 5 | `diagnostics graph --safe --json` | `ok` — live read-only `/me` probe `200` (UPN only; no body, no writeback) |
| 6 | `auth status --json` | `ok` — `mode=delegated`, valid token (`expires_in≈4426s`), scope NAMES only |
| 7 | `construction-agent validate --json` | `ok` — **4/4** (`schema_version=19`, 14 sources / 6 projects, 25 review rules, model routing) |
| 8 | `graph files status --json` | `ok` — registry 14 (sp 10 / od 4), review-queue open **0**, guardrails read-only |
| 9 | `graph files sources --json` | `ok` (dry_run) — 14 sources; matched 8 / unmatched 2 / review_required 2 |
| 10 | `graph files sites --dry-run --json` | `auth_required` (dry_run; no live call) |
| 11 | `graph files drives --source sp_2023projects_23_435_01_tropical_sl --dry-run --json` | `auth_required` |
| 12 | `graph files onedrive --source od_business_bobby_hedrickbrothers --dry-run --json` | `auth_required` |
| 13 | `graph files crawl --source sp_2023projects_23_435_01_tropical_sl --dry-run --json` | `auth_required` |
| 14 | `graph files delta --source sp_2023projects_23_435_01_tropical_sl --dry-run --json` | `auth_required` |
| 15 | `graph files project-match --project tropical --dry-run --json` | `ok` (dry_run; offline; `graph_calls=none`) |
| 16 | `graph files ingestion-policy --source sp_2023projects_23_435_01_tropical_sl --dry-run --json` | `ok` (dry_run; `block_review_required_extraction=true`) |
| 17 | `graph files obsidian --source sp_2023projects_23_435_01_tropical_sl --dry-run --json` | `ok` (dry_run; `source_file_copied_to_vault=false`) |
| 18 | `graph files retrieve --project tropical --query "RFI submittal meeting minutes" --json` | `ok` (offline; `full_text_persisted=false`, `review_routed_excluded=true`) |
| 19 | `graph files no-writeback-proof --json` | `ok` — see below |

Matrix commands 1–4 (`pytest -q`, `ruff check .`, `mypy src`, `compileall`) are the **full-suite gate
deferred to Prompt 17**; this prompt ran narrowest-relevant + touched-module validation (below).

## No-writeback proof — `graph files no-writeback-proof --json`

```json
{
  "command": "graph files no-writeback-proof",
  "ok": true,
  "permission_tightening": "deferred",
  "auth": {
    "configured_delegated_scopes": ["User.Read","Mail.Read","Calendars.ReadWrite.Shared","Files.ReadWrite.All","offline_access"],
    "broad_file_write_scopes_present": ["AllSites.FullControl","Files.ReadWrite.All","Sites.FullControl.All","Sites.Manage.All","Sites.ReadWrite.All"],
    "permission_tightening": "deferred"
  },
  "guard_self_test": { "passed": true, "read_paths_allowed": 24, "mutation_attempts_blocked": 19, "anomalies": [] },
  "static_scan": {
    "dirs_scanned": ["src/hb_assistant/graph","src/hb_assistant/construction/graph","src/hb_assistant/files"],
    "files_scanned": 39, "mutation_method_calls_found": 0, "violations": []
  },
  "contract": { "allowed_methods": ["GET"], "forbidden_methods": ["DELETE","PATCH","POST","PUT"], "never_persist_count": 7 },
  "guardrails": {
    "microsoft_365_writeback": "none",
    "file_mutation_endpoints_blocked": true,
    "no_mutation_method_calls_in_file_services": true,
    "metadata_only_select": true,
    "download_url_never_persisted": true,
    "permission_tightening": "deferred"
  }
}
```

- **Endpoint-guard self-test:** every allowlisted GET permitted (24); every mutation verb/path
  refused before HTTP (19 blocked; 0 anomalies).
- **Source static scan:** 39 files across `graph/`, `construction/graph/`, `files/` — **0** mutating
  method calls, **0** violations.
- The proof itself surfaces the broad-consent risk (`broad_file_write_scopes_present`) and marks
  `permission_tightening: deferred` — consistent with the standing deferral.

## No-secret scan — `diagnostics scan-sensitive --json`

Bounded, content-aware, **redacted-output** scan over repo + Application Support roots.

```json
{
  "implemented": true, "phase": 12,
  "stats": { "files_considered": 1535, "files_scanned": 1034, "files_binary_skipped": 30, "files_oversize_skipped": 3, "files_read_errors": 0, "files_excluded": 468 },
  "note": "Bounded content scan with redacted output fields only; no matched secret values emitted."
}
```

- The scanner emits only `{category, path, line, severity, rule_id, hint}` indicators — **never the
  matched value** (`note`: *no matched secret values emitted*). This is the no-secret guarantee at the
  tool level.
- All indicator hits are heuristic pattern matches in **test fixtures** (fake `env_secret_assignment`
  / `bearer_token` / `oauth_access_token_field` strings used by tests) and **prior evidence/doc text**
  (the literal words "token" / "MSAL cache" in markdown). None point to a real persisted credential in
  runtime source or committed state — matching the established phase-13 baseline.

## No-vault-copy & no-leak attestation (schema + projector enforced)

- V19 `construction_file_extraction_runs` and `construction_graph_download_receipts` carry
  `CHECK(full_text_persisted = 0)`, `CHECK(source_file_copied_to_vault = 0)`,
  `CHECK(raw_download_url_persisted = 0)`.
- `graph files obsidian` guardrails (dry-run capture): `source_file_copied_to_vault=false`,
  `full_text_persisted=false`, `raw_delta_links_rendered=false`, `one_note_per_file=false`,
  `marker_bounded_writes=true` — the projector's output-fence rejects raw delta tokens / signed-URL
  params / `downloadUrl` / auth / PEM / full-text markers.
- `graph files retrieve` guardrails: `excerpt_bounded_redacted=true`, `source_linked=true`,
  `review_routed_excluded=true` — retrieval never bypasses review routing for sensitive files.

## User-provided link resolution (matrix `additional_validations`)

`tests/test_graph_files_link_resolver.py` — **16 passed**. Matrix `required_tests` → repo coverage:

| Matrix id | Repo test |
|---|---|
| `encode_sharing_url_unpadded_base64url` | `test_encode_sharing_url_is_u_prefixed_unpadded_base64url` |
| `resolve_shares_driveItem_folder` | `test_shares_api_folder_success` |
| `resolve_shares_driveItem_file` | `test_shares_api_file_success` |
| `business_onedrive_root_fallback` | `test_onedrive_business_root_fallback` |
| `malformed_url_no_graph_call` | `test_malformed_url_fails_before_graph_call` |
| `no_redeemSharingLink_by_default` | read-only `/shares` path only (no redeem call); covered by `test_shares_api_*_success` + endpoint contract |
| `no_raw_url_or_share_token_persistence` | `test_raw_tokenized_url_persisted_check_is_enforced`, `test_tokenized_url_is_redacted_not_raw`, `test_dry_run_persists_nothing`, `test_apply_persists_redacted_row` |

Referenced evidence artifact present: `05a-user-provided-link-resolution-proof.json`.

## Guardrails honored

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
  "permission_tightening": "deferred"
}
```

## Validation (this prompt)

- `python -m pytest tests/test_graph_files_link_resolver.py tests/test_graph_files_status_and_help.py tests/test_graph_files_retrieval.py` → **29 passed**.
- `ruff check .` → clean · `mypy src` → **Success: no issues found in 142 source files**.
- `construction-agent validate --json` → **4/4**, `schema_version=19`.
- Matrix JSON parses (`json.load`).
- Re-running `diagnostics scan-sensitive` after writing this evidence (placeholders only) introduces
  no real-secret finding.

## Deferred / known

- **Broad `Files.ReadWrite.All` consent retained — tightening deferred** (documented risk,
  `22-deferred-permission-tightening-record.md`); runtime stays read-only at four layers.
- The five Graph-discovery commands degrade to `auth_required` offline; live verification (with a
  files-scoped delegated token) is part of Prompt 17's full matrix.
- **12 pre-existing email-track test failures** (`upsert_email_model_classification` missing on
  `ConstructionStore`) are a separate track, untouched by Phase 06A files work; triage belongs to
  Prompt 17's full-suite gate, not this pilot.
