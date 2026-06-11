# 00 — Repo Truth

- Branch: `feature/phase-10-email-followup-candidate-projection` (never `main`).
- Base / HEAD at start: `e7c1b51` (= `main` = `origin/main`).
- PR 23 merged into `main`: **yes** (`3e5defc` reachable from `main`; merge commit `e7c1b51` = PR #23).
- PR 22 merged into `main`: **yes**.
- Pre-existing dirty tree (NOT this slice, untouched): 11 modified evidence JSON/MD under
  `docs/evidence/construction-intelligence-phase-08b` / `08c`, identical between the two commits, plus
  the untracked planning package. Left alone.
- Local writers on the plain prod DB during the run: DBeaver (GUI reader) and a
  `scheduler ... --environment dev --loop` process (targets the **Dev** root, not the plain prod root).
  The slice only copied the plain prod DB read-only; all apply ran on the `/tmp` copy.

## Relevant existing modules (confirmed)

- Substrate / read models: `construction/email_calendar/projection_registry.py`, `read_models.py`,
  `projection_engine.py`.
- Pipeline + gates: `second_brain/local_ai/pipeline.py`, `projection_activation.py`,
  `email_followup_readiness.py`, `daily_brief_candidate_writer.py`, `source_ref_gate.py`,
  `daily_run.py`, `usefulness_gate.py`.
- Project resolution: `second_brain/local_ai/project_aliases.py` (`resolve_project`, `candidate_tokens`).
- Domain upserts (idempotent): `construction/store/repositories.py`.

## Go/no-go

GO. Existing idempotent tables support the slice → no schema migration required (see 02).
