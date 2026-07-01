# Phase 13 API Contracts

**Proof type:** real API (sanitized JSON committed; Tropical schedule details redacted)

## Artifacts

| File | Description |
|------|-------------|
| `api-named-workbench-before-sync.json` | GET named workbench before operator sync |
| `api-named-workbench-sync.json` | POST sync response (`review_scope=named_baseline`, `synced=true`) |
| `api-named-workbench-after-sync.json` | GET after sync with `psnbri-*` item IDs |
| `api-named-workbench-patch.json` | PATCH status/notes |
| `api-named-workbench-after-patch.json` | GET confirms disposition |
| `api-prior-update-regression.json` | prior_update queue unchanged |
| `api-legacy-baseline-regression.json` | legacy baseline `synced_count=0` |
| `api-cross-slot-isolation.json` | previous_progress_update_baseline separate scope |
| `real-db-proof-summary.json` | capture summary |

## Key contract fields (named sync)

```json
{
  "workbench": {
    "review_scope": "named_baseline",
    "synced": true,
    "comparison_basis": "current_contract_baseline",
    "baseline_context": { "slot_key": "current_contract_baseline", "selection_status": "selected" }
  }
}
```

Item IDs use prefix `psnbri-` (distinct from prior_update `psri-`).
