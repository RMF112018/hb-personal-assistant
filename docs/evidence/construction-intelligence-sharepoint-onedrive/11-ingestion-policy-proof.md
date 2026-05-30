# 11 — Ingestion Eligibility Policy Proof (Phase 06A)

**Prompt:** Prompt 10 — Ingestion Eligibility Policy · **Date:** 2026-05-30
**Posture:** Offline (SQLite + policy + registry); no Graph; no content read; no writeback. Dry-run default.
Reuses the existing review-rule engine + per-source folder policies + the V17 project match.

## Disposition matrix (deterministic, seeded)

`extraction_allowed`/`download_allowed` are True **only** for `eligible`; every other disposition is False.
A review-required row can never allow extraction (DB CHECK `review_required = 0 OR extraction_allowed = 0`).

```json
{
  "command": "graph files ingestion-policy",
  "source": "sp_2023projects_23_435_01_tropical_sl",
  "mode": "dry_run",
  "note": "Deterministic seeded proof (offline; no Graph; no content read). Synthetic items demonstrate each disposition. extraction_allowed/download_allowed True only for 'eligible'.",
  "summary": {
    "total_evaluated": 7,
    "blocked_too_large": 1,
    "blocked_unsupported_type": 1,
    "eligible": 1,
    "low_confidence": 1,
    "manual_approval_required": 1,
    "metadata_only": 1,
    "review_required": 1,
    "review_routed": 3,
    "extraction_eligible": 1
  },
  "disposition_matrix": {
    "blocked_big": {
      "source_id": "sp_2023projects_23_435_01_tropical_sl",
      "drive_item_id": "blocked_big",
      "name": "huge.pdf",
      "drive_id": "D",
      "project_key": "tropical",
      "project_number_detected": null,
      "document_type_detected": null,
      "ingestion_disposition": "blocked_too_large",
      "review_required": false,
      "review_reason": null,
      "download_allowed": false,
      "extraction_allowed": false,
      "reason_codes": [
        "size_over_block:209715200"
      ]
    },
    "blocked_exe": {
      "source_id": "sp_2023projects_23_435_01_tropical_sl",
      "drive_item_id": "blocked_exe",
      "name": "tool.exe",
      "drive_id": "D",
      "project_key": "tropical",
      "project_number_detected": null,
      "document_type_detected": null,
      "ingestion_disposition": "blocked_unsupported_type",
      "review_required": false,
      "review_reason": null,
      "download_allowed": false,
      "extraction_allowed": false,
      "reason_codes": [
        "blocked_extension:exe"
      ]
    },
    "eligible_rfi": {
      "source_id": "sp_2023projects_23_435_01_tropical_sl",
      "drive_item_id": "eligible_rfi",
      "name": "RFI-001.pdf",
      "drive_id": "D",
      "project_key": "tropical",
      "project_number_detected": null,
      "document_type_detected": null,
      "ingestion_disposition": "eligible",
      "review_required": false,
      "review_reason": null,
      "download_allowed": true,
      "extraction_allowed": true,
      "reason_codes": [
        "allowed_extension",
        "matched_project",
        "deep_index_folder"
      ]
    },
    "low_conf": {
      "source_id": "sp_2023projects_23_435_01_tropical_sl",
      "drive_item_id": "low_conf",
      "name": "stray.pdf",
      "drive_id": "D",
      "project_key": "tropical",
      "project_number_detected": null,
      "document_type_detected": null,
      "ingestion_disposition": "low_confidence",
      "review_required": true,
      "review_reason": "low_confidence_project_match",
      "download_allowed": false,
      "extraction_allowed": false,
      "reason_codes": [
        "match_status:low_confidence"
      ]
    },
    "manual_large": {
      "source_id": "sp_2023projects_23_435_01_tropical_sl",
      "drive_item_id": "manual_large",
      "name": "big-export.pdf",
      "drive_id": "D",
      "project_key": "tropical",
      "project_number_detected": null,
      "document_type_detected": null,
      "ingestion_disposition": "manual_approval_required",
      "review_required": true,
      "review_reason": "large_file_manual_approval",
      "download_allowed": false,
      "extraction_allowed": false,
      "reason_codes": [
        "size_warning:31457280"
      ]
    },
    "metadata_cad": {
      "source_id": "sp_2023projects_23_435_01_tropical_sl",
      "drive_item_id": "metadata_cad",
      "name": "model.dwg",
      "drive_id": "D",
      "project_key": "tropical",
      "project_number_detected": null,
      "document_type_detected": null,
      "ingestion_disposition": "metadata_only",
      "review_required": false,
      "review_reason": null,
      "download_allowed": false,
      "extraction_allowed": false,
      "reason_codes": [
        "folder_policy_metadata_only:16-DrawSpecPic"
      ]
    },
    "review_contract": {
      "source_id": "sp_2023projects_23_435_01_tropical_sl",
      "drive_item_id": "review_contract",
      "name": "Master Agreement.pdf",
      "drive_id": "D",
      "project_key": "tropical",
      "project_number_detected": null,
      "document_type_detected": null,
      "ingestion_disposition": "review_required",
      "review_required": true,
      "review_reason": "sensitive:contract",
      "download_allowed": false,
      "extraction_allowed": false,
      "reason_codes": [
        "review_rule:folder-contracts"
      ]
    }
  },
  "guardrails": {
    "external_systems": "read_only",
    "writeback": "none",
    "graph_calls": "none",
    "download_default": "none",
    "extract_default": "none",
    "block_review_required_extraction": true,
    "permission_tightening": "deferred"
  }
}
```

## Disposition meanings

| disposition | review_required | extraction_allowed | example |
| --- | --- | --- | --- |
| eligible | no | **yes** | RFI PDF in a deep-index folder, matched project, small |
| metadata_only | no | no | CAD/native/archive/video/image; metadata-only folder; default |
| manual_approval_required | yes | no | large file in the warning band (≥ 25 MiB) |
| review_required | yes | no | sensitive (contract/financial/legal/...) by review rule or folder |
| low_confidence | yes | no | low-confidence / unmatched project match (V17) |
| blocked_unsupported_type | no | no | executable / unsupported extension |
| blocked_too_large | no | no | file over the block threshold (≥ 100 MiB) |

## Stop-condition check

No M365 writeback, no permission tightening, no source-file copy into Obsidian, no full text persisted,
no raw delta links, **review-routed/sensitive files never auto-extract** (extraction_allowed=False + DB CHECK).
