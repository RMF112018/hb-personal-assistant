# 13 — Obsidian Source Manifests & Project File Registers Preview (Phase 06A)

**Prompt:** Prompt 13 — Obsidian Source Manifests and Project File Registers · **Date:** 2026-05-30
**Posture:** Offline (SQLite only); no Graph; no content read; no writeback. Dry-run default.
No new migration (schema stays at version 19). Mirrors the existing `EmailObsidianProjector`
precedent and reuses `delta_link_fingerprint`; the V2 `ManifestService` (construction-agent/email
track) is intentionally left unchanged.

## What changed

- **`src/hb_assistant/construction/graph/file_obsidian_projection.py`** (new) — `FileObsidianProjector`
  renders **grouped, low-noise** marker-bounded notes from the V5 files SQLite tables. It never
  creates one note per file:
  - **Source Manifest** (one per source) — scope/site/drive/folder ids, active/deleted/file/folder
    counts, last sync, and a **SHA-256 delta-link fingerprint only** (the raw delta token is never
    rendered). Frontmatter carries the package contract keys (`source_id`, `project_key`, `run_id`,
    `generated_at`, `graph_operation_mode`, `writeback: none`, `external_systems: read_only`,
    `permission_tightening: deferred`, `source_traceability: true`).
  - **Project File Register** (one per project) — counts by match status + ingestion disposition and
    a capped (≤50-row) metadata table (name · source · folder · match · disposition · extract ·
    review). No document text, no raw delta links, no source files.
  - **File Review Summary** (one per project) — the sensitive/low-confidence files Prompt 12 routed
    into `construction_review_queue`, grouped by category/sensitivity.
  - **File Processing Receipt** (one per run) — crawl + download/extraction **counts** with
    no-full-text / no-vault-copy / no-signed-URL / no-raw-delta attestations; redacted errors only.
- **`hb-assistant graph files obsidian`** — `--source`/`--project` (optional), `--dry-run/--apply`
  (default dry-run), `--json`. Offline; no Graph client is constructed. Matches the Prompt 17
  validation-matrix command.

## Marker-bounded, idempotent writes

Each note is written inside `<!-- HB-FILES-<KIND>:START -->` / `<!-- HB-FILES-<KIND>:END -->`
markers; re-running **replaces the bounded section in place** (regex DOTALL) — user text outside the
markers is preserved and the block is never duplicated. Dry-run returns the planned absolute paths and
writes nothing.

## Output fence (no raw delta links, tokens, or full text)

Every artifact is fenced at **build** time (so dry-run previews are validated too). A `ValueError` is
raised if the rendered note contains any of: a raw delta token / `deltatoken=` / `?token=` / `&token=`
/ `sig=` signed-URL parameter, the Graph `downloadUrl`, an `Authorization:` / bearer credential,
`access_token` / `refresh_token` / `client_secret`, a PEM private-key block, or a full-document-text
marker. Plain SharePoint item URLs are *not* blanket-banned (traceability), but this projector renders
identifiers/paths only — no `web_url`, no signed URLs.

A seeded test stores a sentinel raw delta token in `source_sync_state`; the rendered Source Manifest
contains only `sha256:<12-hex>` and never the token.

## Dry-run preview (deterministic, seeded; offline)

Seed: one matched + review-routed contract file, one eligible RFI, a folder (excluded), a sync state
carrying a raw delta token, a crawl run, a download receipt, and an extraction run; the contract file
is routed to review via the Prompt 12 router.

```json
{
  "command": "graph files obsidian",
  "mode": "dry_run",
  "ok": true,
  "result": {
    "source_id": "sp_2023projects_23_435_01_tropical_sl",
    "notes_planned": 4,
    "notes_written": 0,
    "sources_referenced": 1,
    "files_referenced": 2,
    "review_items_referenced": 1,
    "paths": [
      ".../07_File_Intelligence/Source Manifests/sp_2023projects_23_435_01_tropical_sl.md",
      ".../07_File_Intelligence/Projects/tropical/File Register.md",
      ".../07_File_Intelligence/Review/tropical File Review.md",
      ".../07_File_Intelligence/Sync Receipts/File Processing Receipt.md"
    ]
  },
  "guardrails": {
    "external_systems": "read_only",
    "writeback": "none",
    "graph_calls": "none",
    "permission_tightening": "deferred",
    "source_traceability": true,
    "full_text_persisted": false,
    "source_file_copied_to_vault": false,
    "raw_delta_links_rendered": false,
    "one_note_per_file": false,
    "marker_bounded_writes": true
  }
}
```

### Rendered Source Manifest (delta fingerprint only)

```markdown
<!-- HB-FILES-SOURCE_MANIFEST:START -->
---
source_id: sp_2023projects_23_435_01_tropical_sl
project_key: tropical
run_id: files-obsidian-<id>
generated_at: <ts>
graph_operation_mode: dry_run
writeback: none
external_systems: read_only
permission_tightening: deferred
source_traceability: true
---

# Source Manifest — 23-435-01 Tropical - S L

## Summary

- Source scope: sharepoint_project_drive_folder
- Source system: sharepoint
- Site ID: <site-id>
- Drive ID: <drive-id>
- Items active: 2
- Files: 2
- Folders: 0
- Items deleted: 0
- Last sync: 2026-05-30T00:00:00+00:00
- Delta fingerprint: sha256:ab12cd34ef56
...
<!-- HB-FILES-SOURCE_MANIFEST:END -->
```

### Rendered Project File Register (capped metadata table)

```markdown
# Project File Register — tropical

## Counts by ingestion disposition
- eligible: 1
- review_required: 1

| Name | Source | Folder | Match | Disposition | Extract | Review |
| --- | --- | --- | --- | --- | --- | --- |
| Master Agreement.pdf | sp_…_tropical_sl | /Contracts | matched | review_required | no | yes |
| RFI-001.pdf | sp_…_tropical_sl | /General | matched | eligible | yes | no |

_Metadata only — no document text, no raw delta links, no source files copied._
```

### Rendered File Review Summary + Processing Receipt (excerpt)

```markdown
# File Review Summary — tropical
## By category
- contract: 1
_Review-routed files cannot extract (enforced by the V18 ingestion CHECK)._

# File Processing Receipt
## Attestations
- Full document text persisted: false
- Source files copied to vault: false
- Signed download URLs cached: false
- Raw delta links rendered: false
```

## Guardrails honored

- **No Microsoft 365 writeback / no Graph calls** — SQLite + rendering only.
- **No source files copied into Obsidian; no full document text persisted.**
- **No raw delta links / tokens / signed URLs / downloadUrl / PEMs** — output-fenced; delta links
  appear only as SHA-256 fingerprints.
- **Not one note per file** — manifests are source-scoped, registers/reviews project-scoped; note
  count is proportional to sources/projects, not files (verified: 40 extra files → still 4 notes).
- **Dry-run default**; `--apply` required to write; writes are marker-bounded and idempotent.
- **Permission tightening deferred** — no delegated scope or broad Graph file consent changed; the
  broad `Files.ReadWrite.All` consent remains a documented, deferred risk (see
  `22-deferred-permission-tightening-record.md`).

## Tests

`tests/test_graph_files_obsidian.py` (6 tests): grouped dry-run (4 notes, no writes); no-one-note-per-
file (40 extra files → still 4 notes); apply marker-bounded + idempotent (section replaced, never
duplicated); output fence (sentinel delta token / downloadUrl / bearer never rendered; only `sha256:`
fingerprint); review summary surfaces the routed sensitive file; CLI offline smoke. Regression:
`test_construction_manifests.py`, `test_email_obsidian_output.py`, `test_repo_sensitive_scan.py`,
`test_mutation_lockout.py` all green (V2 manifests + email track unaffected).
