# Phase 10 (252) — Ollama advisory overlay proof (mock backend)

Bounded advisory overlay: the model may polish `why_it_matters` / `recommended_action` and suggest an attention class (±1 step, only when deterministic confidence is not firm). Deterministic facts (`summary_text`) are never overwritten. A leaky field withholds the entire model layer.

## Overlay result (hash-only receipt)

```json
{
  "status": "ok",
  "degraded_reason": null,
  "enriched_count": 1,
  "model_status": "ok",
  "model_profile_id": "default_extract",
  "model_name": "mistral-nemo:12b",
  "model_receipt_id": null,
  "output_hash": "97ad5c49b200",
  "input_context_hash": "8ad86c6d876b",
  "fallback_used": false
}
```

## Deterministic summary unchanged

- before: Coastal Pipeline submitted Invoice #1842 for Tropical for the pay period ending 05/25/2026 for $58,200.00. It has not been reviewed yet.
- after:  Coastal Pipeline submitted Invoice #1842 for Tropical for the pay period ending 05/25/2026 for $58,200.00. It has not been reviewed yet.

## Model-polished framing (advisory)

- why_it_matters: Unreviewed invoice affecting the next pay cycle.
- recommended_action: Assign the review owner today.
- enrichment_status: model_enriched
