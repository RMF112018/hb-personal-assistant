# Final Handoff — Daily Brief Raw Projection First Slice

## Branch / commit

- Branch: `experiment/phase-10-daily-brief-raw-projection-first-slice`
- Base / merge-base: `4d8ca0717324955dab539ebf0690b5a93d4db6e0` (== main == origin/main)
- Main untouched: yes
- Commits created: one feature commit on the branch (see `git log`).

## Summary

1. **V49 projection activation** — new `projection_activation.run_email_calendar_projection_stage`
   (thin adapter over the projection engine); inserted as the first pipeline stage (special-cased:
   not capped, not a generation stage, a hard failure flips `ok`). Apply projects raw → structured
   before candidate stages.
2. **Calendar candidate projection** — `calendar_prep` now prefers the V49 structured substrate
   (new `ConstructionStore.list_calendar_structured_subjects`, raw-landing fallback) for project
   resolution; persists source-linked `section="calendar"` candidates (existing writer).
3. **Procore ranked candidate projection** — unchanged builder, now activated; promotes ranked
   "why-today" signals, suppresses aggregate sludge/closed into diagnostics only.
4. **Project identity** — deterministic `backfill_project_identity` proof (0 → 6 identities on copy,
   0 conflicts); unresolved calendar projects → `__needs_review__`.
5. **Source-ref / usefulness / contradiction gates** — `usefulness_gate` gains `stage_context` +
   four contradiction checks (calendar/procore/email-followup/synthesis) that force degraded when
   useful source rows exist but candidates are empty.
6. **Daily-run / status surfaces** — `daily_run` forwards stage context, computes the email/follow-up
   data-gap, and emits a `first_slice` status block (raw-free).
7. **Email/follow-up readiness** — new `build_email_followup_data_gap` surfaces "email raw available
   but follow-up projection not yet populated" as an explicit data-gap card (readiness only).

## Files changed

- **Code:** `projection_activation.py` (new), `pipeline.py`, `daily_run.py`, `usefulness_gate.py`,
  `calendar_prep.py`, `email_followup_readiness.py`, `construction/store/repositories.py`.
- **Tests:** `tests/test_phase_10_first_slice_projection_activation.py` (new, 15 tests).
- **Docs:** `docs/architecture/daily-brief-raw-projection-first-slice.md`,
  `docs/runbooks/phase-10-daily-brief-raw-projection-first-slice-runbook.md`.
- **Evidence:** `docs/evidence/phase-10-daily-brief-raw-projection-first-slice/` (`00`–`28`).
- **Planning package:** `docs/planning/phase-10-daily-brief-raw-projection-first-slice-package/`.

## Commands run

- Preflight: `git fetch/checkout -b`, schema/rg baseline.
- Tests: `pytest` (15 new + affected suites, all pass); `compileall`; `ruff check` (clean);
  `ruff format --check` (new module clean); `mypy` (clean on changed modules).
- DB-copy validation: projection dry-run/apply/coverage, calendar/procore dry-run/apply, project
  identity backfill, source-ref coverage, usefulness good + known-bad, integrated daily-run, guard
  columns, leak scan — all on `/tmp` copies.

## Evidence files

`00`–`28` plus `unified-design-contract.md` under
`docs/evidence/phase-10-daily-brief-raw-projection-first-slice/` (counts/hashes/statuses only).

## DB-copy proof

- Production path: `~/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite`
- Copy path: `/tmp/hb-first-slice-<ts>/{audit-copy,evidence-copy,evidence-copy-integrated}.sqlite`
- Projection structured rows (copy): email 405→16,603, thread 223→6,823, calendar 138 (apply).
- Candidate rows (copy): 0 → 31 (6 calendar + 25 procore).
- Source-ref coverage: 100% overall / executive.
- Production changed by this slice: **no** (a concurrent operator `graph mail index` backfill mutates
  production independently — see `23`).

## Safety proof

No external writeback; no email/calendar/Procore/Graph mutation; no cloud LLM; guard columns all 0
(`21`); no raw leakage (`20`, `22`); production opened read-only (`23`).

## Known limitations / residual

See `26-known-limitations.md` and `28-residual-work-audit.md`. No residual work inside the first
slice; out-of-scope next-slice items (email→task extraction, Procore due-date extraction, live
project-identity stage) documented.

## Merge readiness

Ready for review. Branch is isolated from `main`; one feature commit; all in-scope acceptance
criteria proven on DB copies; targeted tests + static checks green.
