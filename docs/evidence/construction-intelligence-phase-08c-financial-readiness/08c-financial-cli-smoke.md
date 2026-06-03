# Phase 08C Financial CLI — Operator Smoke Evidence

Real `hb-assistant second-brain …` invocations (read-only, local-first, advisory only). Captured fields only — no raw payloads.

Generated: 2026-06-03T17:20:54.314842+00:00

| Command | Exit | project_key | advisory_only | no-determination attestation | evidence_paths |
| --- | --- | --- | --- | --- | --- |
| `financial readiness` | 0 | None | True | True | 1 path(s) |
| `financial coverage` | 0 | None | True | True | 1 path(s) |
| `financial exposure-summary` | 0 | None | True | True | 1 path(s) |
| `financial review-items` | 0 | None | True | True | 1 path(s) |
| `financial no-writeback-proof` | 0 | None | True | True | 2 path(s) |
| `data-quality phase-08c-gates` | 0 | None | True | True | 3 path(s) |

## Human-readable sample (`--no-json`)

```
Phase 08C financial no-writeback / no-raw proof
  project: all
  proof passed: True
  checks: {'guard_columns': True, 'money_not_float': True, 'evidence_redaction': True, 'no_live_no_writeback': True}
  proof: docs/evidence/construction-intelligence-phase-08c-financial-readiness/financial-no-writeback-proof.md
```

## Guardrails (uniform across surfaces)

- advisory_only / read_only / local_first / no_external_writeback
- financial_determination_forbidden; explicit no-determination + no-payment + no-live-call attestations
- no raw payloads, prompts, responses, bodies, URLs, or amounts in payloads or evidence

All financial outputs are advisory review aids only — not approvals, claims, entitlements, determinations, or forecasts.
