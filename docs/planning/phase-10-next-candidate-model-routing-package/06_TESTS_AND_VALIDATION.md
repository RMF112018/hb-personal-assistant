# 06 — Tests and Validation

## Objective

Bring the implementation to targeted test readiness and prove it does not regress Phase 10 daily-run/pipeline behavior.

## Scope boundaries

- Fix only failures caused by this package.
- Report pre-existing unrelated failures clearly.
- Do not broaden scope into unrelated cleanup.

Hard constraints:
- Do not modify `main`. Work only on the approved experiment branch for this package.
- Do not merge, rebase main, or imply a merge.
- No cloud LLM submission unless Bobby separately approves it.
- No automatic email send.
- No calendar mutation.
- No Procore writeback.
- No Graph writeback.
- No external writeback.
- No MCP raw exposure.
- No production DB mutation unless explicitly approved.
- No destructive migration unless explicitly approved.
- No credential/auth changes unless explicitly approved.
- No raw email/calendar/Procore/document body content committed to repo.
- No raw prompts, raw model responses, signed URLs, download URLs, join URLs, access tokens, refresh tokens, secrets, credential material, or unsafe HTML committed to repo, evidence, docs, tests, or logs.
- Raw local content may be used only for local operator consumption where explicitly allowed and must never be persisted to guarded candidate/evidence tables.
- Default persisted rows and repo evidence must remain redacted/guarded.
- Any apply/persist behavior must be capped, bounded, idempotent, source-linked, and review-safe.


## Required test groups

Run targeted suites for:
- model eval harness.
- model router/profile config.
- daily brief intelligence.
- local model CLI.
- existing structured-output client.
- existing daily-brief synthesis/render.
- existing pipeline.
- existing daily-run/scheduler if present.
- agent registry.

Example commands, adjust to actual file names:

```bash
.venv/bin/python -m pytest tests/test_phase_10_structured_output.py
.venv/bin/python -m pytest tests/test_local_model_eval.py
.venv/bin/python -m pytest tests/test_local_model_router.py
.venv/bin/python -m pytest tests/test_daily_brief_intelligence.py
.venv/bin/python -m pytest tests/test_phase_10_daily_brief_synthesis.py
.venv/bin/python -m pytest tests/test_phase_10_daily_brief_render.py
.venv/bin/python -m pytest tests/test_phase_10_pipeline.py
.venv/bin/python -m pytest tests/test_phase_10_daily_run.py
.venv/bin/python -m pytest tests/test_agent_registry.py tests/test_second_brain_agents_cli.py
```

Quality commands:

```bash
.venv/bin/ruff check src/hb_assistant tests
.venv/bin/ruff format --check src/hb_assistant tests
.venv/bin/mypy src/hb_assistant
```

If broad ruff/mypy surfaces pre-existing unrelated failures, re-run narrowed changed-scope checks and document the pre-existing failures with proof.

## Required validation matrix

Produce a table:
- Test command.
- Result.
- Failures.
- Root cause.
- Fixed / pre-existing / blocked.

## Stop conditions

- Any package-caused test failure remains unresolved.
- Redaction leakage appears in stdout/evidence.
- Existing daily-run deterministic fallback breaks.
- Router introduces cloud path.

## Commit behavior

Commit fixes if needed:

```bash
git add ...
git commit -m "test(local-ai): validate model routing and brief intelligence"
```

No commit needed if no changes.

## Final response format

Return:
- Test matrix.
- Quality command results.
- Pre-existing failures.
- Package-caused fixes.
