# 00 — Preflight Repo Truth

## Branch / HEAD (verified, not assumed)

- Branch: `feature/phase-10-ollama-candidate-ranking-brief-assembly`
- HEAD: `c81699519da064cc167a8bed1bdf3f1dd37b39c2` (`c8169951`) — matches the package's expected feature tip.

## Working tree

Pre-existing dirty files at session start (NOT this slice; excluded from staging):

- `docs/evidence/construction-intelligence-phase-07a-*`, `…-08b-*`, `…-08c-*` (13 modified files from a concurrent process).
- Untracked planning/evidence dirs from prior phases.

This slice touches only:

- `src/hb_assistant/construction/second_brain/local_ai/daily_brief_presentation.py` (new)
- `src/hb_assistant/construction/second_brain/local_ai/daily_brief_render.py`
- `src/hb_assistant/construction/second_brain/local_ai/daily_run.py` (local browser/appendix item-shape follow-through)
- `src/hb_assistant/construction/second_brain/local_ai/daily_run_html.py` (local browser item-shape follow-through)
- `src/hb_assistant/cli/second_brain.py` (`--section` help text only)
- `tests/test_phase_10_daily_brief_user_facing_render.py` (new)
- `tests/test_phase_10_daily_brief_rendering.py` (updated to the new render contract)
- `docs/evidence/phase-10-daily-brief-user-facing-render-assembly/` (this bundle)

## Schema

No migration added. The render consumes existing V41/V51 read models
(`daily_brief_assembly_runs` / `daily_brief_assembly_sections` / `daily_brief_ranked_candidates` /
`daily_brief_action_candidates`) via store methods that already exist. The "add schema only if render
cannot obtain raw-safe display data" condition was not met → migrator untouched.

## DB selection (strict ambiguity lock)

- Production DB resolved from `PathPolicy.get_db_path()` → the PLAIN config-canonical root
  `~/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite` (1.95 GB).
- `lsof` / `ps` confirmed **no active writer** on the PLAIN DB. The live launchd scheduler runs
  `daily-source-refresh --environment dev` against the `(Dev)` roots only — never PLAIN.
- All mutation-capable commands ran against a `/tmp` copy via `--db`. No command without `--db` was
  run (any such command would migrate the configured prod DB).
