# 20 — Cache Retention Proof (Phase 06A)

**Prompt:** Prompt 11 — Controlled Download and Bounded Extraction · **Date:** 2026-05-30

## Cache policy

- `cache_source_files_after_parse: false` — downloaded source files are not retained.
- Cache lives under `PathPolicy.get_cache_dir("files")` = `{app-support}/cache/files` — outside the repo and the Obsidian vault. Never written into the repo or vault.
- Downloaded content is deleted after parse by default; only `--retain-cache` (debug) keeps it.
- Receipts store `cache_path_redacted` = the basename only (e.g. `rfi1.txt`), never an absolute path and never the raw download URL.

## Proof (from the mocked apply run)

```json
{
  "download_receipt_rfi1": {
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
}
```

`cache_deleted_after_parse = true` for the extracted item; the cache file no longer exists after the run. With `--retain-cache` the file is kept and `cache_deleted_after_parse = false` (see `tests/test_graph_files_controlled_extraction.py::test_retain_cache_keeps_file`).
