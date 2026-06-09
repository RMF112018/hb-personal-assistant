# Failure / Fallback Proof

The pipeline is **fail-closed**: on any model/JSON/schema/source-link/redaction failure the enrichment
is withheld and the deterministic brief is preserved — now with precise, raw-safe diagnostics.

## Observed live fallback (captured during remediation, pre-coercion-fix)

A standalone run where the primary `brief_synthesis` produced schema-invalid output across all
attempts, the single-hop fallback `default_extract` was attempted and also failed, and enrichment was
withheld:

| Field | Value |
| --- | --- |
| status | `schema_invalid` |
| enriched | false |
| route_selected_profile | `brief_synthesis` |
| terminal_profile_id | `default_extract` |
| fallback_used | true |
| metrics.schema_error_category | `schema_invalid` |
| metrics.attempts | 6 (3 primary + 3 fallback) |
| metrics.repair_attempted | true |
| warnings | `fallback_profile_attempted`, `terminal_profile_differs_from_route`, `schema_invalid_after_repair`, `deterministic_fallback_preserved` |
| redaction_passed | true (no raw text surfaced) |

The CLI exits 0 because the deterministic brief is safely preserved (advisory enrichment is optional).

## Fail-closed contract (unit-proven)

`tests/test_daily_brief_intelligence.py` proves each withhold path returns safe diagnostics and no raw
output:

- invalid JSON / schema-invalid → `schema_error_category`, `attempts`, `repair_attempted` (no raw
  error text); repair recovers after one bad output (`attempts==2`).
- all bullets unsourced → `no_source_linked_bullets` with `unknown_source_ids_count`,
  `model_bullets_seen`, `allowed_candidate_count`.
- redaction hit → `redaction_failed` (category codes only).
- model unavailable / daemon unreachable → `model_unavailable` blocker, no silent substitution.
- no candidates → `no_candidates` + `requires_daily_run_apply_to_generate_candidates`.

Post-fix, the same inputs that previously triggered these paths now enrich on the first attempt (see
`live-model-performance-proof.md`); the fail-closed paths remain as the safety floor.
