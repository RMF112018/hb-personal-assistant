# Unified Design Contract — Daily Brief Raw Projection First Slice

> Prompt 01 deliverable. Named without a `04-` prefix to avoid colliding with the
> canonical `04-schema-and-migrations.json` evidence file (Prompt 02).

## Premise (verified from code)

The substrate is fully built but never activated. The audit DB shows projection
runs = 0, structured rows = 0, daily candidates = 0, source refs = 0, project
identity = 0. Therefore this slice is **integration + gate-hardening + evidence**,
reusing existing modules; it adds very little new code.

## Current behavior (as-built)

- **V49 projection** (`construction/email_calendar/projection_engine.py`):
  `reprocess(*, db_path, apply, family, mode, record_receipts)`, `coverage(*, db_path)`,
  `status(*, db_path)`. Dry-run default; `MODE_LIVE` degrades on unmapped, `MODE_ENFORCE`
  raises. Writes `email_calendar_projection_runs` + `email_calendar_projection_coverage`
  receipts on apply. CLI: `email-calendar raw projection-reprocess|coverage|status|inventory`
  (already `--db/--apply/--no-dry-run/--json`; refuses `--apply` without `--db`).
- **Candidate writer** (`daily_brief_candidate_writer.persist_candidate_with_refs`,
  `candidate_source_ref_coverage`): hash-based source refs, idempotent (candidate_id from
  brief_date+section+group_key), writes `daily_brief_action_candidates` + `candidate_source_refs`.
- **Builders already persist source-linked candidates** when `dry_run=False` + `max_persist`:
  `calendar_prep.build_calendar_prep_candidates` (`section="calendar"`),
  `procore_digest.build_procore_action_digest` (`section="procore"`, promote/suppress via
  `procore_ranking.rank_procore_signals`).
- **Gates**: `source_ref_gate.gate_model_candidate_context` + `executive_coverage_ok`
  (EXECUTIVE_SECTIONS = actions/procore/calendar/follow_up/waiting; computes
  `withhold_synthesis`). `usefulness_gate.evaluate_usefulness_gate` reads candidates from the
  store and already downgrades success→degraded on: no useful deterministic section,
  synthesis-without-candidates, executive coverage < 100%, calendar-project-like-all-unresolved,
  egress-not-clean.
- **Orchestration**: `pipeline.py` `STAGE_ORDER = [follow_up_watch, procore_digest,
  calendar_prep, daily_brief_synthesis, daily_brief_render]` (+ optional relationship_candidates);
  builder stages share signature `fn(store, now_utc, limit, dry_run, max_persist, **extra)` and
  return `{"summary": {would_persist, persisted, ...}}`. `daily_run.run_daily_local_agent`
  threads `db_path`/`dry_run`, runs the pipeline, then the usefulness gate.
- **Context packet** (`daily_brief_context_packet.build_daily_brief_context_packet`): read-only;
  already emits `data_gaps` and `source_ref_gate`.
- **Project identity**: V5 tables (`construction_project_identity`,
  `construction_project_source_matches`, `construction_source_locations`), V40
  `construction_project_keyword_registry`; `data_quality/project_identity.ProjectIdentityBackfill`
  (deterministic, conflict→`review_required`); `project_aliases.resolve_project`;
  `calendar_category.resolve_calendar_category` (`__needs_review__` sentinel).

## Design decisions (this slice)

1. **Projection stage placement.** New thin wrapper
   `construction/second_brain/local_ai/projection_activation.py`:
   `run_email_calendar_projection_stage(*, db_path, apply, mode="live")` adapting
   `projection_engine.reprocess` + `coverage` to a stage receipt. Inserted as `STAGE_ORDER[0]`
   and **special-cased** in the pipeline loop (it does not match the builder signature and must
   NOT count toward `max_total_persist` nor `_GENERATION_STAGES`/`brief_freshness`).

2. **Mode per run.** Dry-run/preview pipeline → projection runs coverage-only (no writes).
   Apply pipeline → `reprocess(apply=True)` first so calendar/synthesis read fresh structured
   rows. Projection apply is an idempotent **substrate refresh**, distinct from candidate
   persistence; `daily_run` "dry-run persists nothing" means no *candidate* writes. DB-copy
   validation uses `--db COPY`.

3. **Candidate stages invoked + capped.** Reuse existing builders unchanged in posture:
   `max_persist` required for apply, idempotent skip-existing, `persist_candidate_with_refs`,
   ≥1 source ref per candidate.

4. **Source-ref coverage** checked via `candidate_source_ref_coverage` + `executive_coverage_ok`
   (must be 100% for executive sections for clean success).

5. **Structured = preferred substrate.** `calendar_prep` currently reads legacy
   `calendar_event_index` + raw landing (NOT V49 structured). Add
   `store.list_calendar_prep_source_events_structured(...)` over `calendar_raw_event_structured`
   (+ attendees structured child) with the same key shape; prefer it, fall back to legacy when
   empty. Fixes the current 0.0 project-resolution path (structured carries real `subject`); still
   persists only `title_redacted`. `procore_digest` substrate is the Procore domain (out of scope
   for the email/calendar structured switch).

6. **Project-key coverage / review states.** Wire `ProjectIdentityBackfill` as a deterministic
   read/promotion summary; unresolved/ambiguous → `__needs_review__` + reason codes. No
   model-assisted auto-promotion.

7. **Procore suppression diagnostics-only.** Already enforced by ranking; verify suppressed
   backlog never becomes executive rows; report due-date coverage as data-quality (no fabricated
   dates).

8. **Contradiction → degraded/failed.** Extend `evaluate_usefulness_gate` with an optional
   `stage_context` (forwarded by `daily_run` from per-stage summaries it already holds) and add:
   (a) calendar in-window > 0 but 0 candidates & not all-excluded-with-reason;
   (b) procore open > 0 & promoted > 0 but 0 candidates;
   (c) email/thread rows in window > 0 but 0 follow-up candidates & status != data_gap
   (add `data_gap` status to follow_up_watch if absent);
   (d) `withhold_synthesis` true while synthesis succeeded (uses already-fetched gate report).

9. **Email/follow-up = readiness only.** Compute readiness counts; emit data-gap card
   "email raw content available but follow-up projection not yet populated" via the existing
   `data_gaps` mechanism. **Not** building a new NLP follow-up agent.

10. **Status JSON** surfaces projection/candidate/coverage/project-key/calendar/procore/
    email-followup/data_gaps/usefulness_verdict/degraded_reasons — counts/status/reason-codes only.

## Explicitly NOT built

Cloud LLM routes; any external/Graph/Procore/calendar/email writeback; full semantic email
follow-up extraction agent; destructive migration; production DB mutation during validation;
raw private content in any artifact.

## New modules / functions (minimal)

- NEW `construction/second_brain/local_ai/projection_activation.py`.
- NEW `store.list_calendar_prep_source_events_structured(...)` in
  `construction/store/repositories.py`.
- EDIT `pipeline.py` (stage insertion + special-case), `daily_run.py` (forward projection
  receipt + stage_context, status fields), `usefulness_gate.py` (stage_context + 4 checks),
  `calendar_prep.py` (prefer structured reader), `follow_up_watch` (data_gap status if absent),
  status/data-gap surfacing where gaps exist.

No duplicate logic introduced; all heavy lifting reuses existing engine/writer/gate/ranking code.
