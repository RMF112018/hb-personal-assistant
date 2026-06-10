# 240 — Phase 10 daily-brief usefulness substrate

Records the durable architecture established by the daily-brief usefulness repair
(`fix/daily-brief-usefulness-repair`, baseline `main@dbff6e89`). Evidence:
`docs/evidence/daily-brief-usefulness-repair/`. Driver: a production DB-usefulness audit (schema
V45) found a run could report `success` while the brief was operator-useless — calendar project
resolution 0.0, 0 daily-brief candidates for the target date, candidate source-ref coverage 0.0, and
Procore executive rows dominated by 3,592 aggregate-"sludge" rows.

## Diagnosis (repo-truth, not the audit's surface reading)

- A **project alias resolver already existed and worked** (`project_aliases.resolve_project` +
  `resources/config/project_aliases.seed.yaml`: `TWN→tropical`, `Wellington→the-wellington`,
  `Hilltop/Alton Hilltop→alton-hilltop-pbg`, `PGA→pga-modern-garage`). The 0.0 calendar resolution
  was downstream of **candidates = 0** and of resolving against the **hashed `subject_redacted`**
  placeholder (no spaces, ~27 chars) rather than the real subject.
- **Source-ref coverage 0.0** because the projection stages persisted candidates but never wrote
  `candidate_source_refs` (the table + idempotent upsert existed, unused).
- **Procore sludge** was emitted on purpose: the digest produced `"{count} open {signal_type}
  signals"` aggregates with no ranking and no "why today", and surfaced `observation_closed`.

## The substrate (deterministic, before any model)

A layered, read-model + gate substrate that sits *before* prompt/model work:

| Module (`construction/second_brain/local_ai/…`) | Role |
|---|---|
| `calendar_category.py` | Adds the project / internal_company / internal_training / internal_time_off / needs_review / unknown **category** dimension. The project arm **delegates** to `project_aliases.resolve_project_alias` (single canonical matcher); never forks alias logic. Low-confidence project-looking text → `__needs_review__` (review-safe), never an invented project. |
| `procore_ranking.py` | `rank_procore_signals` scores each open signal; **promotes** overdue / due-soon / recent / source-change-linked / financially-material / high-critical and **suppresses** stale high-count aggregates and semantically-closed (`*_closed`) signals. Financial materiality reuses the project-health dimension map. |
| `daily_brief_candidate_writer.py` | The **single persistence contract**: `persist_candidate_with_refs` owns candidate-id derivation, hash-only `candidate_source_refs` upserts, and idempotency. Calendar + Procore both route through it — no per-stage hand-rolling. `candidate_source_ref_coverage` computes coverage. |
| `source_ref_gate.py` | `gate_model_candidate_context` feeds the model ONLY source-linked candidates and reports overall + executive coverage; `drop_unsupported_bullets` enforces that a model bullet may claim a meeting/risk/action only if it cites a source-linked candidate; `withhold_synthesis` when candidates exist but none are linked. |
| `usefulness_gate.py` | `evaluate_usefulness_gate` decides whether an apply run may stay `success`: ≥1 useful deterministic section, 100% executive source-ref coverage, project-like calendar not all unresolved, Procore top rows not aggregate sludge, no synthesis/deterministic contradiction. |

### Data flow

```
calendar_prep ─┐                                   ┌─ source_ref_gate ─→ model context (linked only)
               ├─→ persist_candidate_with_refs ─────┤
procore_digest ┘   (daily_brief_action_candidates    └─ usefulness_gate ─→ daily_run status verdict
                    + candidate_source_refs)
```

- `calendar_prep` resolves category from the **real raw subject** (read from
  `calendar_event_raw_content` for resolution only; the redacted title is what's persisted) so the
  persisted `project_key` is non-zero in production.
- `procore_digest` persists only ranked **promoted** rows as executive `procore` candidates; the
  aggregate backlog becomes a `suppressed_backlog` diagnostic (never an executive row).
- `build_daily_brief_context_packet` now exposes a `source_ref_gate` block and a gated
  `candidates_by_section`; `synthesize_daily_brief` fail-closes (`status=blocked`,
  `no_source_linked_context`) when all rows are withheld.
- `run_daily_local_agent` runs the usefulness gate after projection + synthesis and before
  `is_fresh_success`; a failing apply-mode `success` is downgraded to `partial` (warning
  `usefulness_gate_failed:<reasons>`), which preserves the last-successful pointer and prevents
  `daily-brief-latest.html` overwrite. Status JSON + payload carry a `usefulness_gate` block.

## Schema decision — REUSE V45, no migration

Every required candidate field maps onto existing V45 storage, so **no migration** was added:

| Field | Storage |
|---|---|
| id / brief_date / section | `daily_brief_action_candidates` (id from brief_date+section+group_key) |
| project key OR internal category | `project_key` (real key, or sentinel `__internal_company__` / `__internal_training__` / `__internal_time_off__` / `__needs_review__` / `__unassigned__`) |
| rank / urgency | `priority` (lower = higher) |
| why-today | `reason_redacted` |
| next action | `recommended_next_action` |
| confidence / quality | `confidence` |
| source-ref link(s) | `candidate_source_refs` (candidate_type=`daily_brief_action`) |
| safety / data-quality flags | derived deterministically at gate time (needs_review sentinel, missing-ref, suppression) |

The category sentinels are `__…__`-prefixed so any consumer can treat them as "not a real project"
(the context packet's calendar labeling enforces this).

## Invariants preserved

No Microsoft 365 / Graph / Procore / calendar writeback; no cloud model; dry-run default for the
builders; raw subjects used for resolution are never persisted/logged/emitted; persisted rows + status
+ evidence are hash/enum/count only (guard columns CHECK(=0)); the local model is fail-closed and
advisory — deterministic source-linked candidates are the source of truth.
