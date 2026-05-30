# 19 — Large-File Policy Proof (Phase 06A)

**Prompt:** Prompt 10 — Ingestion Eligibility Policy · **Date:** 2026-05-30

## Thresholds (file_ingestion_policy.seed.yaml)

- `extract_warning_bytes` = 26214400 (25 MiB)
- `block_extract_bytes` = 104857600 (100 MiB)

## Bands (large files never auto-extract)

| size | disposition | extraction_allowed |
| --- | --- | --- |
| ≤ warning | (normal disposition by other signals) | per disposition (eligible only) |
| > warning, ≤ block | `manual_approval_required` | **no** (operator approval required) |
| > block | `blocked_too_large` | **no** (too large to extract; metadata only) |

## Seeded examples

```json
{
  "manual_approval_required": {
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
  "blocked_too_large": {
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
  }
}
```

A large file is **never** extraction-eligible: the warning band routes to `manual_approval_required`
(review_required, extraction_allowed=False) and over-block routes to `blocked_too_large`
(extraction_allowed=False). Enforced in `IngestionEligibilityEvaluator` + the V18 CHECK.
