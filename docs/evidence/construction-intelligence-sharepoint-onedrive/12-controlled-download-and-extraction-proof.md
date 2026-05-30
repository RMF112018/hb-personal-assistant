# 12 — Controlled Download & Bounded Extraction Proof (Phase 06A)

**Prompt:** Prompt 11 — Controlled Download and Bounded Extraction · **Date:** 2026-05-30
**Posture:** Read-only; dry-run default; only V18-eligible files; explicit --download/--extract flags; no full text persisted; no source copy into Obsidian; @microsoft.graph.downloadUrl never used/cached.

## Flow

1. Read V18 ingestion decisions; only `extraction_allowed` (eligible, non-review) items proceed. Review-required/blocked/metadata-only/manual/low-confidence are skipped (`blocked_*`).
2. Drive-aware `GET /drives/{drive_id}/items/{item_id}/content` (guard-asserted, bounded by `--max-bytes`) streamed to a cache outside repo/vault; content hashed (sha256).
3. `ParserRouter` -> bounded excerpt -> scrubbed (emails/phones/long tokens masked) -> persisted as `text_excerpt_redacted` (DB CHECK `full_text_persisted = 0`).
4. Download + extraction receipts persisted; cache deleted after parse (unless `--retain-cache`).

## Mocked apply run (eligible `rfi1` extracted; review-required `contract1` blocked)

```json
{
  "command": "graph files extract",
  "source": "sp_2023projects_23_435_01_tropical_sl",
  "mode": "apply (mocked client)",
  "note": "Deterministic mocked proof (live download degrades to auth_required: token expired). Synthetic content; the planted email/token are masked in the persisted excerpt. Cache outside repo/vault, deleted after parse.",
  "report": {
    "command": "graph files extract",
    "mode": "apply",
    "source": "sp_2023projects_23_435_01_tropical_sl",
    "do_download": true,
    "do_extract": true,
    "summary": {
      "total": 2,
      "blocked_review_required": 1,
      "extracted": 1,
      "downloaded": 1
    },
    "items": [
      {
        "source_id": "sp_2023projects_23_435_01_tropical_sl",
        "drive_item_id": "contract1",
        "drive_id": "b!tropical-drive",
        "name": null,
        "project_key": "tropical",
        "disposition": "review_required",
        "status": "blocked_review_required",
        "downloaded": false,
        "extracted": false,
        "bytes_written": null,
        "sha256": null,
        "char_count": 0,
        "excerpt_preview": null,
        "cache_deleted": false,
        "error_redacted": null
      },
      {
        "source_id": "sp_2023projects_23_435_01_tropical_sl",
        "drive_item_id": "rfi1",
        "drive_id": "b!tropical-drive",
        "name": null,
        "project_key": "tropical",
        "disposition": "eligible",
        "status": "extracted",
        "downloaded": true,
        "extracted": true,
        "bytes_written": 127,
        "sha256": "acb7af08e819813ae95247ec7c471e7021758cf28de4261730b9893f40036c17",
        "char_count": 106,
        "excerpt_preview": "RFI 07: please respond by Friday. PM email [email-redacted] token [token-redacted]. Spec section 03 30 00.",
        "cache_deleted": true,
        "error_redacted": null
      }
    ]
  },
  "persisted_download_receipts": [
    {
      "receipt_id": "f53b7fe9-fef4-49e9-90d2-00ca80b2dc57",
      "source_id": "sp_2023projects_23_435_01_tropical_sl",
      "drive_id": "b!tropical-drive",
      "drive_item_id": "rfi1",
      "project_key": "tropical",
      "mode": "apply",
      "download_attempted": true,
      "download_completed": true,
      "bytes_written": 127,
      "sha256": "acb7af08e819813ae95247ec7c471e7021758cf28de4261730b9893f40036c17",
      "cache_path_redacted": "rfi1.txt",
      "cache_deleted_after_parse": true,
      "status": "extracted",
      "error_redacted": null,
      "created_utc": "2026-05-30T15:33:16.497253+00:00",
      "raw_download_url_persisted": false,
      "source_file_copied_to_vault": false
    }
  ],
  "persisted_extraction_runs": [
    {
      "extraction_id": "139d811c-01e9-4a6a-b42f-e3bb4a5007dd",
      "source_id": "sp_2023projects_23_435_01_tropical_sl",
      "drive_id": "b!tropical-drive",
      "drive_item_id": "rfi1",
      "project_key": "tropical",
      "parser_name": "files-router",
      "parser_version": "files-router-1",
      "content_hash": "acb7af08e819813ae95247ec7c471e7021758cf28de4261730b9893f40036c17",
      "extraction_status": "ok",
      "text_excerpt_redacted": "RFI 07: please respond by Friday. PM email [email-redacted] token [token-redacted]. Spec section 03 30 00.",
      "char_count": 106,
      "full_text_persisted": false,
      "review_required": false,
      "error_redacted": null,
      "created_utc": "2026-05-30T15:33:16.494197+00:00"
    }
  ],
  "guardrails": {
    "external_systems": "read_only",
    "writeback": "none",
    "download_url_cached": false,
    "full_text_persisted": false,
    "source_copied_to_vault": false,
    "cache_outside_repo_and_vault": true,
    "block_review_required_extraction": true,
    "permission_tightening": "deferred"
  }
}
```

The planted email and 32-char token in the source content are masked in the persisted excerpt (`[email-redacted]` / `[token-redacted]`); the raw values appear nowhere.

## Stop-condition check

No M365 writeback; no permission tightening; no source-file copy into Obsidian (CHECK); no full text persisted (CHECK); no raw download URL persisted (CHECK); review-required files never downloaded or extracted; live download degrades to `auth_required`.
