# Daily Brief Raw Projection First Slice

**Status:** implemented (Phase 10 first slice).
**Evidence:** `docs/evidence/phase-10-daily-brief-raw-projection-first-slice/`.

## Problem

The V49 email/calendar raw → structured projection substrate and full Procore raw payloads landed,
but the daily brief produced no source-linked executive actions: the production DB showed structured
projection rows present yet `daily_brief_action_candidates = 0`, `candidate_source_refs = 0`, and no
gate flagged the contradiction. The candidate builders already worked — the apply pipeline had simply
never run against the PLAIN production DB (the dev scheduler targets a separate `(Dev)(Dev)` DB).

## Design

Integration over existing surfaces — minimal new code.

### 1. Projection activation stage

`construction/second_brain/local_ai/projection_activation.py` —
`run_email_calendar_projection_stage(*, db_path, apply, mode="live")` is a thin, raw-free adapter
over `email_calendar.projection_engine.reprocess` + `coverage`. It returns a stage receipt
(`status`, `mode`, `raw_rows_by_family`, `structured_rows_by_family`, coverage, `unmapped_counts`,
`source_quality_distribution`, `degraded_reason`, guard flags). `no_raw_rows` is an honest
non-failure; an unmapped/parity family degrades/fails without a partial projection (engine `live`
mode never raises, never partially projects); a family with raw rows but zero structured after apply
is `zero_structured_after_apply`.

The pipeline (`pipeline.py`) inserts `email_calendar_projection` as `STAGE_ORDER[0]`, **special-cased**
in the loop like the render stage: it does not match the builder signature, does not count toward
`max_total_persist`, and is not in `_GENERATION_STAGES` (so it never flips `brief_freshness`). A hard
projection failure flips the pipeline `ok`. Dry-run pipeline → coverage-only; apply → reproject first
so the candidate stages read fresh structured rows in the same run.

### 2. Structured = preferred substrate (calendar)

`calendar_prep` resolved projects from the raw landing (`calendar_event_raw_content`). It now prefers
the V49 structured table via `ConstructionStore.list_calendar_structured_subjects()` (real
subject/location, keyed by `event_index_id`), falling back to the raw landing for any unprojected
event. Only `title_redacted` is ever persisted; the real subject is used for resolution only. The
summary reports a `subject_substrate` split for evidence.

### 3. Candidate persistence (existing, now activated)

`calendar_prep.build_calendar_prep_candidates` and `procore_digest.build_procore_action_digest`
already persist source-linked candidates via `daily_brief_candidate_writer.persist_candidate_with_refs`
(hash-based refs, idempotent, `max_persist`-capped) when `dry_run=False`. Procore promotes ranked
"why-today" signals and suppresses aggregate sludge / semantically-closed signals into diagnostics
(never executive rows). Unknown/ambiguous calendar projects become `__needs_review__` with reason codes.

### 4. Project identity first pass

`data_quality/project_identity.backfill_project_identity` (deterministic, conflict→`review_required`,
idempotent) populates `construction_project_identity` / `construction_project_source_matches` from
local source truth. Run as a proof on the copy; not wired as a live daily stage (alias resolution
already reaches 100% project-key coverage in-window).

### 5. Usefulness / contradiction gates

`usefulness_gate.evaluate_usefulness_gate` gains an optional `stage_context` (forwarded by `daily_run`
from the per-stage summaries it already holds — apply runs only). New checks, each respecting explicit
exclusion/suppression so a legitimately-empty section never false-fails:

- `calendar_window_nonempty_but_no_candidates` — events in window the stage would persist, yet zero
  calendar candidates landed.
- `procore_promotable_but_no_candidates` — open AND promotable signals, yet zero procore candidates.
- `email_rows_but_empty_followup_no_data_gap` — email substrate exists, follow-up layers empty, and no
  data-gap acknowledgment.
- `synthesis_success_without_any_source_linked_candidate` — source-ref gate withholds synthesis
  (candidates exist, none source-linked) yet synthesis reported ok.

### 6. Email/follow-up data-gap readiness

`email_followup_readiness.build_email_followup_data_gap` (counts only) classifies the email-substrate-
vs-follow-up-layers state into `populated` / `data_gap` / `no_source` / `not_configured` and emits a
data-gap card. It feeds both the status surface and the gate's check (c) — so empty follow-up is an
explicit data gap, never a silent "nothing to do".

### 7. Status surface

`daily_run` emits a `first_slice` block (counts/statuses/reason-codes only) in the run result and
status file: projection, candidates total/by-section, source-ref + project-key coverage, calendar,
Procore promote/suppress, email/follow-up readiness, data gaps, usefulness verdict, degraded reasons.

## Safety

Local-only; no Graph/Procore/email/calendar/cloud-LLM writeback; dry-run default; apply requires
explicit `--db`/cap; guard columns stay 0; receipts/status/evidence carry no raw values. Validation
runs against `/tmp` DB copies; production is opened read-only.

## Validation

See evidence bundle `00`–`28` and the runbook
`docs/runbooks/phase-10-daily-brief-raw-projection-first-slice-runbook.md`.
