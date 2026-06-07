# MASTER IMPLEMENTATION PROMPT — Frontend UI/UX Shell, Masonry Layout, and End-User Copy Remediation

You are working on the `hb-personal-assistant` repository.

Repository path:

```text
/Users/bobbyfetting/hb-personal-assistant
```

## Objective

Implement the frontend production-readiness remediation package under:

```text
docs/evidence/frontend-ui-ux-shell-layout-implementation-package/
```

Primary objective: fix the frontend app shell and primary screens before enhanced features are added.

The implementation must:

1. lock the app shell to the viewport;
2. make main content scroll independently;
3. keep sidebar footer/status controls pinned and accessible;
4. remove local-dev/test-harness copy from normal UI;
5. remove disabled Chat from visible production navigation;
6. add a future-ready Data Quality footer indicator;
7. refactor Today, Projects, and My Items into responsive dashboard/masonry-style grids;
8. rewrite Settings and Admin/Data Health surfaces into end-user copy;
9. centralize shared status/error/empty/loading copy;
10. add copy regression coverage and closeout evidence.

## Non-scope

Do not implement Microsoft Graph auth, Procore auth, new sync, source-system writes, retrieval/MCP/memory changes, Obsidian writes, or Chat.

## Execution order

Run prompts `P00` through `P09` in order. Do not skip P0 acceptance criteria. If repo truth has advanced, adapt file names and line references to current code but preserve the objective.

## Required preflight

Before edits, run:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log --oneline -n 30
cat pyproject.toml
cat frontend/package.json
find frontend/src -maxdepth 4 -type f | sort
```

Document branch, HEAD, dirty tree state, frontend package scripts, and any divergence from package baseline.

## Required final validation

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
npm run test
npm run copycheck

cd ..
python -m pytest tests/test_fastapi_analytics_app_shell.py
python -m pytest tests/test_fastapi_analytics_auth_onboarding.py tests/test_fastapi_analytics_settings.py tests/test_fastapi_analytics_connection_setup.py
```

If a command is unavailable, document the exact failure and use the closest available validation without hiding the limitation.

## Required final report

Use `09_CLOSEOUT_REPORT_TEMPLATE.md`. Include changed files, validation results, manual smoke results, copycheck output, screenshots/evidence references, and explicit safety confirmation that no external systems were modified.
