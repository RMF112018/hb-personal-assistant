# 15 — Operator Command Surface Proof (Phase 06A)

**Prompt:** Prompt 15 — Operational CLI and Runbooks · **Date:** 2026-05-30
**Posture:** Offline / read-only; no Graph; no writeback. No new migration (schema stays at version 19).

## What changed

- **`hb-assistant graph files status`** (new, read-only) — operator status dashboard: delegated-auth
  posture (scope names only, no tokens; no interactive login), source registry counts, V5 projection
  count, open review-queue size, and standing guardrails. This is the `status` command the package
  Operator Runbook and the Prompt 17 validation matrix call.
- **Hardened `graph files` group help** — `graph files --help` now states the dry-run-default + opt-in
  side-effect-flag contract (`--apply` / `--download` / `--extract`) and the read-only / no-writeback /
  deferred-permission guardrails.
- **Runbook** — `docs/runbooks/phase-06a-operational-sharepoint-onedrive-workflows.md` (10-section
  operator runbook, dry-run-first for every command).
- **README "Repository Status"** — added the Phase 06A block.

## Command surface → side-effect flags → dry-run default

| Command | Side-effect flags | Default | Notes |
| --- | --- | --- | --- |
| `status` | — | read-only | offline posture dashboard |
| `no-writeback-proof` | — | read-only | behavior-level no-writeback proof |
| `sources` | `--apply` | dry-run | V5 source projection |
| `sites` / `site resolve` / `drives` / `onedrive` | `--dry-run/--apply` | dry-run | discovery receipts on apply |
| `link resolve` | `--dry-run/--apply` | dry-run | Shares API; raw URL never persisted |
| `index` / `crawl` / `delta` | `--dry-run/--apply` | dry-run | metadata only; deltaLink → SQLite, fingerprint rendered |
| `project-match` | `--dry-run/--apply` | dry-run | low-confidence/unmatched → review |
| `ingestion-policy` | `--dry-run/--apply` | dry-run | disposition before any fetch |
| `extract` | `--dry-run/--apply`, `--download/--no-download`, `--extract/--no-extract` | dry-run; download/extract off | review-required skipped; bounded redacted excerpt; cache deleted after parse |
| `review-queue` | `--dry-run/--apply` | dry-run | idempotent enqueue |
| `obsidian` | `--dry-run/--apply` | dry-run | grouped marker-bounded notes |
| `retrieve` | — | read-only | bounded redacted excerpts; review-routed excluded |

Every write-capable command defaults to **dry-run**; persistence/content fetch/parse require explicit
opt-in. (Regression-guarded by `tests/test_graph_files_status_and_help.py`.)

## `graph files status --json` (capture)

```json
{
  "command": "graph files status",
  "ok": true,
  "delegated_auth": {
    "mode": "delegated",
    "token_acquisition": "on_demand",
    "note": "Offline status; a live token is acquired only by --apply/--download workflows.",
    "configured_delegated_scopes": ["User.Read", "Mail.Read", "Calendars.ReadWrite.Shared", "Files.ReadWrite.All", "offline_access"],
    "broad_file_write_scopes_present": ["AllSites.FullControl", "Files.ReadWrite.All", "Sites.FullControl.All", "Sites.Manage.All", "Sites.ReadWrite.All"],
    "permission_tightening": "deferred"
  },
  "sources": {
    "registry_total": 14,
    "by_system": { "sharepoint": 10, "onedrive": 4 },
    "enabled": 14,
    "resolved": 1,
    "pending": 13,
    "projected_v5": 14
  },
  "operational": { "review_queue_open": 0, "store_error": null },
  "guardrails": {
    "external_systems": "read_only",
    "writeback": "none",
    "graph_calls": "none",
    "microsoft_365_writeback_enabled": false,
    "dry_run_default": true,
    "permission_tightening": "deferred",
    "broad_consent_note": "Files.ReadWrite.All consent retained at tenant; runtime read-only; tightening deferred (documented risk)."
  }
}
```

The status command surfaces no tokens (scope names only) and writes nothing.

## `graph files no-writeback-proof --json` (capture)

```json
{
  "command": "graph files no-writeback-proof",
  "ok": true,
  "permission_tightening": "deferred",
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

## Deferred broad-permission risk (documented)

`status.delegated_auth.broad_file_write_scopes_present` makes the over-broad consent explicit:
`Files.ReadWrite.All` (and related Sites scopes) remain consented at the tenant and are **not** tightened
in this phase. The runtime is read-only at four layers (YAML policy, MSAL scope request, Python adapter,
SQLite CHECK) and `no-writeback-proof` passes. Remediation is deferred and recorded in
`22-deferred-permission-tightening-record.md`.

## Guardrails honored

- **No Microsoft 365 writeback / no Graph calls / no token leakage** — `status` is offline and posture-
  only; `no-writeback-proof` is green.
- **Dry-run is the default** for every write-capable command; verified by a regression test.
- **No full document text / signed URLs / downloadUrl / raw delta links** — unchanged from Prompts
  11–14; reaffirmed in the group help and runbook.
- **Permission tightening deferred** — no delegated scope changed; broad consent retained (documented).

## Tests

`tests/test_graph_files_status_and_help.py` (7 tests): status posture + guardrails; status leaks no
tokens; write-capable commands (`ingestion-policy`, `obsidian`, `extract`) default to `dry_run`; group
help documents `--apply`/`--download`/`--extract` + dry-run; `status --help` ok. `construction-agent
validate` 4/4 (schema_version=19). The matrix command `graph files status --json` returns `ok: true`.
