# N8C-20 — git status (pre-commit)

Branch: `ops/nas-second-brain-n8c-20-quality-maintenance-20260707T225036Z`  Base: `621e09b6` (N8C-19).

## `git status --porcelain` (before staging)
```
 M docs/evidence/construction-intelligence-phase-08c-financial-readiness/currency-completeness-report.json
 M docs/evidence/construction-intelligence-phase-08c-financial-readiness/exposure-mart-preview.json
 M docs/evidence/construction-intelligence-phase-08c-financial-readiness/financial-readiness-agent-proof.json
 M docs/evidence/construction-intelligence-phase-08c-financial-readiness/financial-source-coverage-matrix.json
 M docs/evidence/construction-intelligence-phase-08c-financial-readiness/forecast-readiness-gates.md
 M docs/evidence/construction-intelligence-phase-08c-financial-readiness/forecast-readiness-proof.json
 M docs/evidence/construction-intelligence-phase-08c-financial-readiness/wbs-cost-code-coverage-report.json
 M src/hb_assistant/cli/main.py
 M src/hb_assistant/construction/analytics/api.py
 M src/hb_assistant/nas_mcp/broker.py
 M src/hb_assistant/nas_mcp/profile.py
 M src/hb_assistant/nas_mcp/tool_registration.py
 M src/hb_assistant/store/migrator.py
?? docs/evidence/nas-second-brain-n8c/20260707T225036Z/
?? src/hb_assistant/cli/quality.py
?? src/hb_assistant/obsidian_mcp/quality_evaluator.py
?? src/hb_assistant/obsidian_mcp/quality_models.py
?? src/hb_assistant/obsidian_mcp/quality_repository.py
?? src/hb_assistant/store/assistant_quality_tables.py
?? tests/test_fastapi_analytics_quality.py
?? tests/test_nas_mcp_quality.py
?? tests/test_quality_cli.py
?? tests/test_quality_evaluator.py
?? tests/test_quality_models.py
?? tests/test_quality_repository.py
?? tests/test_quality_v111_migration.py
```

## Staging allowlist (explicit paths — NO `git add -A`)

The 12 new quality files + 6 additive-modified files + this evidence dir are staged by explicit path.
The 7 forecasting-bundle-regenerated `docs/evidence/…phase-08c…/*.json` artifacts are left UNSTAGED
(they are not part of N8C-20).

## `local-sensitive/` gitignore
```
docs/evidence/nas-second-brain-n8c/20260707T225036Z/local-sensitive/README.md
```
