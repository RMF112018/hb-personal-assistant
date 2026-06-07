# Final Validation Closeout and Handoff

## Objective

Run full backend/frontend/model/Obsidian/MCP validation, write evidence, update README/architecture docs, and provide next-step handoff.

## Repo-truth baseline

- Repository: `RMF112018/hb-personal-assistant`
- Audited HEAD from GitHub connector/static repo inspection: `c52cc757b062fe4baf918bd7227dad5e669e3899`
- App version observed: `1.3.0`
- Frontend package version observed: `0.0.0`
- SQLite schema head observed: `V40`
- Latest merged PR observed: PR #3, `Codex/frontend shell layout p00`
- Local dirty state: not verifiable from this package generation context; local agent must run `git status --short` before editing.
- Local launcher/scheduler runtime state: not verifiable from this package generation context; local agent must run the launcher/scheduler commands listed in Prompt 00.

Repository truth is authoritative. This package is an implementation guide only. Reconfirm every touched path and command before editing.


## Phase classification

Closeout

## Files likely affected

- `pyproject.toml`
- `src/hb_assistant/cli/main.py`
- `src/hb_assistant/cli/second_brain.py`
- `src/hb_assistant/cli/launcher.py` only if status integration is necessary
- `src/hb_assistant/cli/vault.py` or new vault command module
- `src/hb_assistant/store/migrator.py`
- `src/hb_assistant/construction/second_brain/`
- `src/hb_assistant/construction/local_ai/`
- `src/hb_assistant/construction/action_intelligence/`
- `src/hb_assistant/construction/obsidian/`
- `src/hb_assistant/construction/analytics/api.py`
- `src/hb_assistant/resources/json/`
- `src/hb_assistant/resources/config/`
- `resources/json/`
- `resources/yaml/`
- `resources/sql/`
- `docs/architecture/`
- `docs/runbooks/`
- `docs/evidence/construction-intelligence-phase-10-local-action-intelligence/`
- `tests/`
- `frontend/src/`


## Implementation steps

1. Reconfirm current repo truth and changed files before editing.
2. Add or update contracts/seeds first when this prompt introduces a new policy or output shape.
3. Implement the smallest vertical slice that can be tested with local fixtures.
4. Keep dry-run behavior as the default for commands that can create local records or files.
5. Add unit tests for success, blocked, unavailable dependency, invalid schema, stale schema, and no-raw/no-writeback behavior.
6. Add proof/evidence command output under `docs/evidence/construction-intelligence-phase-10-local-action-intelligence/`.
7. Update architecture/runbook documentation only after tests pass.

## Guardrails

- Local-first. No external LLM/API dependency is required for Phase 10.
- No Graph writeback, Procore writeback, email send, calendar mutation, Teams/Slack/SMS/push delivery, or source-system update.
- No raw email body, raw calendar payload, raw Procore payload, raw document text, raw model prompt, raw model response, signed URL, download URL, token, secret, or arbitrary path persistence.
- Local model outputs are advisory candidate records unless explicitly accepted by the user.
- High-stakes items involving contract, legal, financial, payment, claim, entitlement, safety, or schedule impact are signals requiring human review, never determinations.
- Model direct access to Graph, Procore, local filesystem outside allowlisted folders, arbitrary SQL, subprocess, browser, network, or MCP write tools is prohibited.
- Structured model output must validate against a JSON Schema/Pydantic contract before any database write.
- Every accepted candidate must retain source references, confidence, model profile, prompt/template version, input window metadata, and review status.
- Dev and Production outputs, receipts, vector stores, job queues, and Obsidian writes must remain isolated by environment profile.


## Stop conditions

Stop and report if:

- current repo truth materially differs from this package and changes the implementation target;
- any output requires raw restricted content persistence;
- any command performs external writeback;
- any model output bypasses schema validation;
- an accepted task/commitment can exist without source references;
- Obsidian writes touch content outside managed markers;
- MCP exposes arbitrary SQL, raw content, or write tools.

## Exact validation commands

Run the relevant subset after this prompt and include command output in evidence:

```bash
python -m compileall src tests
ruff check src tests
mypy src
pytest -m "not live and not integration and not manual"

cd frontend
npm install
npm run lint
npm run build
npm test -- --run
```

Phase 10 command checks, once implemented:

```bash
hb-assistant second-brain local-model status --json
hb-assistant second-brain ai-jobs status --json
hb-assistant second-brain ai-jobs run --dry-run --max-items 10 --json
hb-assistant second-brain action-intel extract-fixture --fixture tests/fixtures/local_ai/email_task_candidate_001.json --json
hb-assistant vault status --json
hb-assistant vault index --dry-run --json
hb-assistant second-brain mcp packet build --packet-type daily_brief --date 2026-06-07 --json
hb-assistant construction-agent data-quality no-writeback-proof --json
hb-assistant second-brain mcp data-quality no-raw-access-proof --json
hb-assistant second-brain mcp data-quality no-writeback-proof --json
```


## Evidence outputs

Write prompt-specific evidence under:

`docs/evidence/construction-intelligence-phase-10-local-action-intelligence/`

Include JSON and Markdown proof where possible. Include counts, hashes, source refs, command exits, warnings, deferred items, blocker classifications, and guardrail summary.

## Expected commit summary guidance

```text
Phase 10 30: Final Validation Closeout and Handoff

- Implemented: <summary>
- Safety: local-only, no raw persistence, no writeback
- Validation: <commands>
- Evidence: docs/evidence/construction-intelligence-phase-10-local-action-intelligence/<file>
```
