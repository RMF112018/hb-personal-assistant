# 09 Closeout and Handoff

## Final Closeout Criteria

The implementation package is complete only when:

- P0 and P1 gaps are closed or replaced with repo-truth evidence that they were already fixed.
- P2 gaps are closed or explicitly deferred with owner/date/reason.
- Browser smoke passes for Today, Projects, My Items, Admin, and Settings.
- Frontend `npm install`, `npm run lint`, `npm run typecheck`, and `npm run build` pass without hidden peer-dependency workarounds.
- Backend targeted analytics tests pass.
- New `tests/test_fastapi_analytics_today.py` exists or the current repo has equivalent Today coverage with evidence.
- No active chat UI exists.
- No raw/secrets/writeback violations are present in UI, backend serialization, tests, or evidence.
- Runbooks accurately distinguish implemented behavior from planned behavior.

## Final Handoff Summary Requirements

The final implementation session should report:

- branch and final HEAD;
- commits created;
- files changed;
- gaps closed by severity;
- validation commands and results;
- browser smoke results;
- any remaining blockers;
- whether source code, migrations, operator DB, auth cache, Obsidian vault, or external systems were modified;
- next recommended phase if any.
