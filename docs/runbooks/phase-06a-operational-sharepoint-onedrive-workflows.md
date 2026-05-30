# Phase 06A Operational SharePoint / OneDrive File Intelligence Runbook

## 1. Overview

Operator runbook for the read-only `hb-assistant graph files` command surface (Phase 06A). It pulls
**metadata and bounded, redacted excerpts** from delegated Microsoft Graph (SharePoint/OneDrive) into
local SQLite + Obsidian. It never writes back to Microsoft 365, never copies source files into the
vault, never persists full document text, and never renders raw delta links or tokens. **Dry-run is the
default** for every command that could write SQLite, a cache file, or an Obsidian note.

## 2. Safety Model

- Microsoft 365 mutation allowed: **false** (no upload/create/update/delete/move/copy/share/label/
  check-in-out/permission change).
- Dry-run default: **true** — side effects require explicit opt-in flags (see §3).
- Full source document text persisted: **false** (bounded redacted excerpts only; SQLite CHECK
  `full_text_persisted = 0`).
- Raw delta links / tokens / signed URLs / `@microsoft.graph.downloadUrl` persisted or rendered:
  **false** (delta links surface only as `sha256:<12>` fingerprints).
- Source files copied into Obsidian: **false**.
- Broad Graph file permission (`Files.ReadWrite.All`) tightening: **deferred** (documented risk; the
  runtime is read-only at four layers — YAML policy, MSAL scope request, Python adapter, SQLite CHECK).

### Side-effect opt-in flags

| Flag | Effect | Commands |
| --- | --- | --- |
| `--apply` (vs `--dry-run`) | Persist to SQLite / discovery receipts / driveItem index / sync state / ingestion decisions / review-queue rows / Obsidian notes | `sites`, `site resolve`, `drives`, `onedrive`, `index`, `link resolve`, `crawl`, `delta`, `project-match`, `ingestion-policy`, `review-queue`, `obsidian` |
| `--apply` (bare; default off) | Persist the canonical V5 source projection | `sources` |
| `--download` (default off) | Controlled content fetch to a cache **outside** repo+vault, deleted after parse | `extract` |
| `--extract` (default off; requires `--download`) | Bounded **redacted** parse into an excerpt | `extract` |

## 3. Status & Registry

```bash
hb-assistant graph files status --json      # delegated-auth posture, source counts, review-queue, guardrails
hb-assistant graph files sources --json     # dry-run: V5 projection plan (add --apply to persist)
```

## 4. Discovery (read-only, metadata-only)

```bash
hb-assistant graph files site resolve --source sp_2023projects_23_435_01_tropical_sl --dry-run --json
hb-assistant graph files drives       --source sp_2023projects_23_435_01_tropical_sl --dry-run --json
hb-assistant graph files onedrive     --source od_business_bobby_hedrickbrothers     --dry-run --json
hb-assistant graph files link resolve --url "<sharepoint-or-onedrive-link>"          --dry-run --json
```

Add `--apply` to persist redacted discovery receipts. Live commands degrade to `auth_required` when no
cached delegated token is present (no interactive login is triggered).

## 5. Index & Sync (dry-run → apply)

```bash
hb-assistant graph files index --source <key> --dry-run --json   # then --apply to persist driveItems
hb-assistant graph files crawl --source <key> --dry-run --json   # bounded baseline crawl
hb-assistant graph files delta --source <key> --dry-run --json   # incremental; deltaLink stays in SQLite (fingerprint only)
```

## 6. Project Match & Ingestion Policy

```bash
hb-assistant graph files project-match    --project tropical --dry-run --json   # low-confidence/unmatched -> review
hb-assistant graph files ingestion-policy --source <key>     --dry-run --json   # disposition per file before any fetch
```

Sensitive / large / low-confidence files are marked `review_required` and **never auto-extract**.

## 7. Controlled Download / Extraction

```bash
# Dry-run plan (no download, no parse, no SQLite write):
hb-assistant graph files extract --source <key> --dry-run --json
# Apply with explicit opt-in (review-required/blocked files are skipped):
hb-assistant graph files extract --source <key> --apply --download --extract --json
```

Content streams to a cache outside the repo+vault, is hashed, parsed into a **bounded redacted**
excerpt, and the cache is deleted after parse (`--retain-cache` for debugging only). `downloadUrl` is
never used or cached; full text is never persisted.

## 8. Sensitive Review Routing

```bash
hb-assistant graph files review-queue --source <key> --dry-run --json   # then --apply to enqueue (idempotent)
```

Routes contracts, financials, claims, notices, legal, HR/personnel, insurance/bonding, safety, medical,
disputes, cost/schedule impact, and low-confidence matches; review-routed files cannot extract.

## 9. Obsidian Output & Source-Linked Retrieval

```bash
hb-assistant graph files obsidian --source <key> --dry-run --json   # preview; --apply writes marker-bounded notes
hb-assistant graph files retrieve --project tropical --query "RFI submittal meeting minutes" --json
```

Obsidian notes are grouped (per-source manifest, per-project register, review summary, processing
receipt) — never one note per file — and output-fenced. Retrieval returns bounded redacted excerpts
with source traceability (drive item, web URL, project, parser output, processing receipt); review-
routed files are excluded.

## 10. Evidence / Audit, Troubleshooting & Maintenance

```bash
hb-assistant graph files no-writeback-proof --json        # behavior-level no-writeback proof
construction-agent validate --json                        # schema/registry/rules/model checks (4/4)
```

The full operator validation set is in `resources/json/phase_06a_files_validation_matrix.json`
(exercised at Prompt 17). Evidence bundles: `docs/evidence/construction-intelligence-sharepoint-onedrive/`.

**Troubleshooting:** live commands returning `auth_required` → no cached delegated token (run an
`--apply` workflow from an interactive shell to acquire one); `requires_rebaseline` on `delta` → a 410
stale delta token, re-run `crawl --apply`; empty `status` counts → run `sources --apply` to project the
registry.

**Maintenance notes (future agents):** do not add Microsoft 365 writeback; do not tighten or change
delegated scopes / remove `Files.ReadWrite.All` consent in this phase (deferred); do not copy source
files or persist full document text into Obsidian; keep dry-run the default; reconcile package
instructions against repo truth (code/tests/evidence) before editing.
