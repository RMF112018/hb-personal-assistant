# 01 — N8C-15 baseline & carry-forward

## N8C-15 committed this session
- Commit `a5441dab` — `feat(nas): add n8c workflow routing` (plain, no AI trailer). Explicit-path staged
  (2 modified + 4 new source + 5 new test + evidence dir `.../20260707T173145Z/`). `local-sensitive/`
  git-ignored & unstaged. Working tree clean; not pushed.
- Gate reconstructed after the prior session's background runs were lost: full N8C-1→N8C-15 regression
  subset (614 test functions / 68 files) exit-0 across three batches; N8C-12 finality guard passed;
  schedule canary exit-0; ruff clean; evidence secret-scan clean; 67 confirmations verified.

## Carry-forward into N8C-16
- Schema head remains **V108**; `store/migrator.py` untouched.
- N8C-16 consumes the frozen N8C-15 `WorkflowRouter` / registry read-only — no change to those modules.
- Kill-switch + RO-snapshot patterns mirror the N8C-14 answer-draft MCP layer exactly.
