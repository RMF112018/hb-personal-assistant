# 01 — N8C-8 baseline + carry-forward

## N8C-8 committed this run (Part 1)
- Commit: `208e7b68` — `feat(nas): add n8c decision memory layer` (plain message, no AI trailer).
- Parent: `b99151f1` (N8C-7). Committed locally in worktree
  `/Users/bobbyfetting/hb-pa-n8c02-20260705T200705Z`; **not pushed**.
- Pre-commit verification: 68 focused N8C-8 tests passed; ruff clean on in-scope files (zero delta vs
  N8C-7 on `api.py`; `store/` + test backlog is pre-existing out-of-scope); `scripts/test-schedule.sh -q`
  passed (`SCHED_EXIT=0`).
- Staged set: exactly the 10 modified + 10 untracked intended paths + the N8C-8 evidence bundle
  (`docs/evidence/nas-second-brain-n8c/20260706T203541Z/`, 14 md files); `local-sensitive/` is
  git-ignored and was not staged. No blind `git add -A`.

## Carried into N8C-9
- Schema head at base = 104. N8C-9 advances it to 105 additively.
- Advisory records available to review: assistant_claims (V100), assistant_enrichment_* (V101),
  assistant_context_pack_* (V102), assistant_memory_* (V103), assistant_decision/preference/open_loop
  records (V104).
- Patterns mirrored: `store/assistant_*_tables.py` (`V1NN_STATEMENTS` + shared `_PROVENANCE_CHECK`),
  `obsidian_mcp/*_models.py` (sha256[:24] ids), `*_repository.py` (`conn=` reads, lineage supersede),
  `*_extractor.py` (read-only preview vs apply), CLI `--dry-run/--apply`, `_assistant_env`+`role_dep` API,
  and the `nas_mcp` read-only snapshot (`_ro_uri` + `PRAGMA query_only=ON`) + default-ON kill switch.
