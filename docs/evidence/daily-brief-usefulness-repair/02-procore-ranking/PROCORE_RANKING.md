# Priority 2 — Procore Signal Ranking & Aggregate Suppression (Prompt 02)

## What changed

- **New** `src/hb_assistant/construction/second_brain/local_ai/procore_ranking.py`:
  `rank_procore_signals(signals, *, now_utc, last_success_utc=None)` → `RankedSignal` per signal with
  `rank_score`, `rank_reasons`, `why_today`, `suppression_reason`, `is_aggregate_sludge`,
  `is_semantically_actionable`, `source_change_linked`, `recent`, `due_soon`, `overdue`,
  `owner_linked`, `financial_materiality`, `priority`, `promoted`.
  - **Promotion** (clear "why today"): overdue, due-soon, newly observed (recent / since last
    successful brief), source-change-linked, financially material, or high/critical importance.
  - **Suppression**: everything else → `no_why_today_stale_backlog` (aggregate sludge when also no
    owner/no change link); `*_closed` / resolved signals → `semantically_closed` up-front so
    **`observation_closed` never surfaces as an open action**.
  - Financial materiality reuses the existing project-health dimension map (`_dimensions_for`) — no
    duplicated classification. Deterministic: `now_utc`/`last_success_utc` injected, no clock read.
- **New read-model** `repositories.list_procore_action_signals_for_ranking` — adds owner /
  source-change / first-seen / last-seen to the safe-enum set for ranking. The opaque
  `owner_entity_key` / `source_change_event_id` are converted to booleans by the ranker and **never
  emitted** (proved by a no-leak test). Free-text (title/summary/metadata) still excluded.
- **Refactored** `procore_digest.py`: ranks signals, persists only top-ranked **promoted** rows as
  executive `procore` candidates (capped by `--limit`, then `--max-persist`), and demotes the
  aggregate backlog to a `suppressed_backlog` diagnostic labeled by suppression reason. The audit's
  giant "1,265 open inspection items"-style counts now live in diagnostics, never as top rows. Added
  `executive_rows` (source-linked) + `suppressed_backlog` to the payload and ranking metrics to
  `summary`. Removed the orphaned `_IMPORTANCE_PRIORITY` constant.

## Demonstration (synthetic, in the integration test)

1 overdue high signal + 50 stale medium backlog + 1 `observation_closed` →
`promoted_count=1`, `suppressed_count=51`, `aggregate_sludge_count=50`,
`semantically_closed_count=1`; `executive_rows` = the single promoted, source-linked row;
backlog appears only in diagnostics.

## Tests

- `tests/test_phase_10_procore_ranking.py` — 12 passed (overdue / due-soon / recent / high /
  source-change / financial promotion; stale-aggregate + observation_closed suppression;
  deterministic order; executive vs suppressed split; cap enforcement; no owner-key leak).
- `tests/test_phase_10_procore_digest.py` — 16 passed (no regression; existing guardrail contracts —
  dry-run zero writes, apply-requires-max-persist, idempotency, guard columns, no-forbidden-keys,
  empty-clean, synthesis fail-closed, CLI — all preserved).
- `ruff check` on changed files: clean.
