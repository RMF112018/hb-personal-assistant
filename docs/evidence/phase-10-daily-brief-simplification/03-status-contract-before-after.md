# 03 — Status contract: before / after

## Before (252)

- Single user-facing `status` owned by the run orchestration: LLM synthesis + the legacy candidate-
  count usefulness gate. Degraded synthesis → `deterministic_success_synthesis_degraded`; MEI withheld
  surfaced its own banner.
- New Today contributed only a counts-only `new_today` summary and **inherited** the legacy status,
  which it then passed into the render model — so a synthesis-degraded run forced a "Some sources were
  degraded" warning above an otherwise-useful New Today brief. Confusing.

## After (253)

- Legacy top-level `status` **preserved unchanged** (scheduler / status readers / tests).
- Additive, product-facing `daily_brief` block owns the user-facing status:

```json
{
  "daily_brief": {
    "primary_surface": "new_today",
    "status": "success | degraded | failed",
    "operator_usable": true,
    "degraded_reasons": [],
    "new_today": {
      "total_items": 0, "by_family": {}, "email_degraded": false,
      "model_enrichment_status": "used | withheld | unavailable | not_requested",
      "deterministic_fallback_used": false
    },
    "diagnostics": {
      "legacy_status": "<top-level status>",
      "legacy_synthesis_status": "ok | degraded | diagnostic_only",
      "model_enriched_intelligence_status": "diagnostic_only",
      "legacy_candidate_sections_available": true
    }
  }
}
```

## Live validation evidence (real `/tmp`-copy run, brief 2026-06-12)

The real run demonstrates the separation exactly:

| Field | Value |
|---|---|
| top-level `status` (legacy) | `deterministic_success_synthesis_degraded` |
| `daily_brief.diagnostics.legacy_synthesis_status` | `degraded` (confined to diagnostics) |
| `daily_brief.status` (product) | `degraded` |
| `daily_brief.degraded_reasons` | `["email_followup_degraded", "projection_coverage_degraded"]` |
| `daily_brief.new_today.total_items` | 42 (email 4, calendar 16, procore 22) |
| `daily_brief.new_today.model_enrichment_status` | `not_requested` |
| `daily_brief.diagnostics.model_enriched_intelligence_status` | `diagnostic_only` |

The product `degraded` is driven **only** by New Today reasons (email follow-up + projection coverage)
— the degraded LLM synthesis did **not** contribute to the product status; it is diagnostics. This is
the crux behavior, observed live. (The crux success-path — synthesis degraded + useful New Today →
`daily_brief.status=success`, no warning — is locked by the unit/render tests in
`tests/test_phase_10_daily_brief_simplified.py`.)
