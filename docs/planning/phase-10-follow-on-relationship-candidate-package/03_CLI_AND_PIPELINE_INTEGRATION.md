# 03 — CLI and Conservative Pipeline Integration

## Objective

Expose the relationship candidate engine through a first-class CLI and, only if safe, add an optional daily-pipeline integration hook that does not disrupt the in-progress daily pipeline pilot.

## Scope

CLI is required. Pipeline integration is optional and must be conservative.


## Non-Negotiable Constraints

- Target branch: `experiment/local-agent-family-proof` unless Bobby explicitly directs otherwise.
- Do not modify `main`; do not merge; do not retarget PRs.
- Treat live repo truth and DB truth as authoritative over this package.
- This package assumes the production-like daily pipeline pilot is already in progress or complete; do **not** re-implement scheduler, polished brief delivery, Obsidian delivery, or daily pipeline automation except for minimal integration hooks explicitly scoped here.
- No cloud LLM submission unless Bobby separately approves it.
- No automatic email send.
- No calendar mutation.
- No Procore writeback.
- No Graph writeback.
- No external writeback.
- No MCP raw exposure.
- No production DB mutation unless Bobby explicitly approves it.
- No destructive migration unless Bobby explicitly approves it.
- No credential/auth changes unless Bobby explicitly approves it.
- No raw email/calendar/Procore/document body content committed to repo, tests, evidence, docs, or logs.
- No raw prompts, raw model responses, signed URLs, download URLs, join URLs, access tokens, refresh tokens, secrets, credential material, or unsafe HTML committed to repo, evidence, docs, tests, or logs.
- Default persisted rows and repo evidence must remain redacted/guarded.
- Any apply/persist behavior must be capped, bounded, idempotent, source-linked, review-safe, and disabled by default.
- Raw local content may appear only in explicitly approved local operator-consumption surfaces and never in committed evidence.


## Likely Files

- second-brain CLI command registration modules
- `src/hb_assistant/construction/second_brain/local_ai/relationship_candidates.py`
- `src/hb_assistant/construction/second_brain/local_ai/pipeline.py`
- CLI tests under `tests/`

## Required CLI

Add:

```bash
hb-assistant construction second-brain relationship-candidates scan   --db <path>   --as-of <iso>   --limit <n>   --scan-threads <n>   --scan-events <n>   --min-confidence <float>   --dry-run   --summary   --json
```

Apply form:

```bash
hb-assistant construction second-brain relationship-candidates scan   --db <copy.sqlite>   --as-of <iso>   --apply   --max-persist <n>   --summary   --json
```

## CLI Requirements

- Dry-run default.
- `--apply` fails closed without `--max-persist` with a stable error code and nonzero exit.
- `--json` emits machine-readable output.
- `--summary` is useful for operator review but redacted.
- Invalid parameters fail closed with stable error codes.
- No raw output in default CLI response.

## Optional Pipeline Hook

Only implement if it does not conflict with active Checkpoint 6 work:

- Add a relationship-candidates stage after calendar prep and before daily-brief synthesis, or leave as a standalone command and document the deferred hook.
- Default pipeline behavior should not persist relationship rows unless pipeline apply caps explicitly cover this stage.
- Any pipeline hook must preserve existing `second-brain pipeline run` behavior and tests.
- If the daily pipeline pilot is actively modifying pipeline files, do **not** touch them; document the future integration point instead.

## Required Tests

- CLI dry-run writes zero rows.
- CLI apply without cap exits 2 or repo-equivalent stable fail-closed code.
- CLI apply with cap persists bounded rows.
- CLI re-run is idempotent.
- CLI JSON shape stable.
- Pipeline regression tests still pass.
- If pipeline hook is added, stage ordering and cap handling are tested.


## Required Validation Layers

Every implementation prompt must validate at three layers:

1. **Code-level validation**
   - unit tests for new deterministic functions;
   - CLI wiring tests;
   - regression tests for Phase 10 Checkpoints 1-current;
   - `ruff check` on changed files and agreed broad scope;
   - `ruff format --check` or equivalent format check;
   - `mypy` on changed modules and agreed package scope.

2. **Workflow-level validation**
   - actual CLI dry-run against a DB copy or temp DB;
   - controlled apply/write only on DB copy or safe temp path;
   - idempotency proof;
   - row-count proof before/after;
   - fail-closed proof for missing caps, stale schema, missing source refs, and invalid parameters;
   - status/output proof with structured JSON.

3. **Agent-output validation**
   - deterministic relationship output shape;
   - reviewable/source-linked output;
   - operator usefulness in daily brief context;
   - no forbidden raw egress;
   - redacted evidence only;
   - raw local content only where explicitly approved.


## Stop Conditions

- Active local daily pipeline work conflicts with pipeline file edits.
- Existing CLI architecture would require large unrelated refactor.
- Pipeline integration would change default apply semantics unexpectedly.

## Commit Behavior

Commit expected: yes, after tests pass.

Commit message suggestion:

```bash
git commit -m "Add relationship candidate CLI surface"
```

## Final Response Format

Return:

- CLI command and flags;
- pipeline integration status: implemented / deferred with reason;
- validation commands and results;
- guardrail proof;
- commit SHA.

