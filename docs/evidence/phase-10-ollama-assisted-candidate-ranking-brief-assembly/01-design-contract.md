# Phase 10 V51 — Design Contract

## Pipeline

```
review-queue rows (V50, authoritative)
  → candidate ranking packet  (raw-free, source-gated, hashed)
  → feedback calibration      (bounded, aggregate, no negative transfer)
  → [optional] bounded Ollama advisory  (validated, alias-mapped, leak-scanned)
  → deterministic ranking engine  (authoritative; model bounded)
  → [optional] advisory similarity edges  (review-only)
  → deterministic section assembly
  → status / usefulness gate / persistence
```

## Hard gates (enforced in code + tests)

1. **Additive only** — V51 adds 5 tables + store helpers; no V50 lifecycle semantics or render path
   changed.
2. **Deterministic authoritative** — lifecycle exclusion, source-ref gate, and raw-safety always beat
   model advice. The model only adjusts after deterministic eligibility is established.
3. **Source-ref coverage non-negotiable** — source-missing actionable candidates are withheld;
   accepted-missing-source lowers coverage and degrades the run + trips the usefulness gate.
4. **Similarity never auto-merges** — edges are `review_duplicate_candidate` evidence only.
5. **Deterministic brief always survives** — model unavailable/withheld/unsafe → deterministic ranked
   brief preserved, `deterministic_fallback_used=true`, honest `model_layer_status`.
6. **`--no-client` is success** — full deterministic run; only a fail-closed packet (raw leak) fails.
7. **Hash-only receipts** — model calls reuse `local_model_run_receipts`; V51 stores only receipt
   ids/hashes/status.

## Explicit tunable constants (surfaced in `policy_version`)

- `MAX_RANK_MOVEMENT = 3` — the model may move a candidate at most 3 positions from its
  deterministic-only rank. Deterministic-close items sit at adjacent ranks, so they reorder freely; a
  clearly-higher deterministic candidate can never be leapfrogged beyond the bound.
- `DET_CLOSE_THRESHOLD = 0.08` — "close" threshold on the normalized 0..1 scale.
- `MIN_FEEDBACK_SAMPLES = 5` — minimum reviewed outcomes in a family before calibration applies.
- `MAX_CALIBRATION_ADJUSTMENT = ±0.10` — clamp on the normalized 0..1 scale (±10 points on 0..100).

### Scale convention

Deterministic / feedback / model scores are on a **0..100** scale (README `final_score` formula).
The `0.08` / `0.10` thresholds are applied on the **normalized 0..1** scale (neutral feedback = 50;
±0.10 → feedback in [40, 60]). `final = 0.75·det + 0.20·feedback + 0.05·model` (model present), else
`0.80·det + 0.20·feedback`.

## Scoring components (deterministic base, 0..100, clamped)

lifecycle state (stale/accepted/review boosts) · due proximity · waiting-on-others nudge ·
project/Procore risk · imminent meeting prep · project-linked · source-ref strength · confidence ·
duplicate-copy penalty. Tie-breakers: final ↓ → deterministic ↓ → lifecycle priority → due bucket →
project_key → candidate id.
