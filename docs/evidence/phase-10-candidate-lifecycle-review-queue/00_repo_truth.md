# 00 — Repo-Truth Audit (Phase 10 Candidate Lifecycle / Review Queue / Feedback)

Raw-free. Paths, SHAs, table/column names, counts, and reason codes only.

## Git state

- Audit run date: 2026-06-11
- Working branch: `feature/phase-10-candidate-lifecycle-review-queue`
- Base branch: `feature/phase-10-email-followup-candidate-projection`
- HEAD at branch creation: `512d103f598f8aa29e35da9aad4d167ed80c87f6`
- `main` == `origin/main` == HEAD == `512d103f` (branch cut from the merged tip)
- Email follow-up candidate projection slice is **merged and reachable** on `main`
  (`483d0cc6 feat(second-brain): project email follow-up candidates into daily brief (246 v1)`).
- Dirty tree at start (NOT part of this slice, will NOT be staged):
  `docs/evidence/construction-intelligence-phase-08b-*` (2 files),
  `docs/evidence/construction-intelligence-phase-08c-*` (9 files).
- Untracked (this slice's source package): `docs/planning/phase-10-candidate-lifecycle-review-queue-package/`.

## Runtime / DB-writer context

- A live process is running: `hb-assistant scheduler run daily-source-refresh --environment dev --loop`.
  The `--environment dev` scheduler pins the `(Dev)` application-support root, not the plain
  production root used by this audit. `dbeaver` holds a read handle on the plain prod DB.
- Mitigation (per prior guidance on active prod writers): all apply/idempotency checks run on
  `/tmp` copies only; the read-only schema audit opens the prod DB with `?mode=ro` (no copy,
  provably non-mutating); the unchanged proof is captured as prod-DB SHA at validation time plus
  the structural fact that no slice code path targets the prod DB.

## Existing review / lifecycle primitives (verified)

- Schema: `src/hb_assistant/store/migrator.py` — `LATEST_SCHEMA_VERSION = 49`; latest applied
  migration on prod is `49 v49_email_calendar_full_raw_content_and_projections`.
- Phase 10 substrate created in **V41**; Phase 10A review metadata added in **V43**
  (`task_candidates`/`commitment_candidates`: `reviewed_utc`, `reviewed_by`,
  `review_note_redacted`, `snoozed_until_utc`; `candidate_review_events`:
  `changes_json_redacted`, `snoozed_until_utc`, `reviewer_ref`).
- 13 guard columns shared across all Phase 10 tables: `PHASE_10_GUARD_COLUMNS`
  (`construction/second_brain/local_ai/schema.py`), each `CHECK(<col> = 0)`.
- Service: `construction/second_brain/local_ai/candidate_review.py` —
  `accept_candidate` / `reject_candidate` / `ignore_candidate` (→ `suppressed`) /
  `snooze_candidate` / `edit_candidate` / `export_review_queue`, unified through `_apply_decision`,
  auditing via `candidate_review_events`.
- CLI: `cli/second_brain.py` — `second-brain review` (accept/ignore/reject/snooze/edit/export,
  single + batch) and `phase-10 review-candidate --promote`. New work attaches a `candidates`
  Typer group; review verbs remain unchanged.
- Promotion: deterministic idempotent accepted ids `acc-task:{cid}` / `acc-commit:{cid}`
  (ON CONFLICT DO NOTHING). Commitment promotion exists. Source refs link via `candidate_id`
  (indirect through `candidate_source_refs`).
- Follow-up: `follow_up_watch.py` (`classify_watch_status`, `run_follow_up_watch_scan`,
  dry-run default + `max_persist` cap).
- Gates: `usefulness_gate.evaluate_usefulness_gate` (12 ordered contradiction checks),
  `source_ref_gate.gate_model_candidate_context` (fail-closed; 100% executive coverage required).
- Daily brief: `daily_brief_context_packet.build_daily_brief_context_packet`,
  `daily_brief_render.render_daily_brief`, `daily_brief_html` (external-asset scan, fail-closed).

## Tests already protecting behavior

`tests/test_phase_10a_candidate_review.py`, `tests/test_phase_10a_candidate_review_cli.py`,
`tests/test_phase_10_acceptance_promotion.py`, `tests/test_phase_10_follow_up_monitor.py`,
`tests/test_phase_10_daily_brief_synthesis.py`, `tests/test_phase_10_usefulness_gate.py`,
plus `test_phase_10_email_followup_candidate_projection.py`, `test_phase_10_daily_brief_rendering.py`.

## Convergence-not-rebuild decision

The implementation **extends** the existing Phase 10A surface: it does not modify
`candidate_review.py` task/commitment status semantics, the `second-brain review` verbs, promotion,
or follow-up. The unified lifecycle read model **consumes** existing `review_status` columns and a
new append-only lifecycle overlay; it does not create dual truth for task/commitment status.

## Migration decision (detail in 01_schema_audit.json)

A minimal additive **V50** is justified: `candidate_review_events` is structurally
task/commitment-only and lacks `subject_type` (it has `candidate_type` ∈ {task, commitment}),
`target_subject_*`, `duplicate_group_key`, `effective_until_utc`, and any
daily-brief/accepted/watch subject support. No existing table can represent cross-family merge,
group suppression, or close/reopen across families idempotently. New tables are append-only and
carry the 13 guard columns. No materialized `candidate_review_queue` table is added — the queue is
a computed read model.
