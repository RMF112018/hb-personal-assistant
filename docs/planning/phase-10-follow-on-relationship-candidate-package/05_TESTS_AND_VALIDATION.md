# 05 — Tests and Validation Hardening

## Objective

Run and harden the complete code-level, workflow-level, and agent-output validation suite for the relationship candidate engine and prior Phase 10 checkpoints.

## Scope

Tests/fixes only. Do not expand feature scope.


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


## Required Validation Commands

Adjust exact paths to repo truth, but run the equivalent of:

```bash
cd /Users/bobbyfetting/hb-personal-assistant

python -m pytest   tests/test_phase_10_acceptance_promotion.py   tests/test_phase_10_follow_up_monitor.py   tests/test_phase_10_procore_digest.py   tests/test_phase_10_daily_brief_synthesis.py   tests/test_phase_10_calendar_meeting_prep.py   tests/test_phase_10_daily_brief_rendering.py   tests/test_phase_10_pipeline.py   tests/test_agent_registry.py   tests/test_second_brain_agents_cli.py   tests/test_phase_10_relationship_candidates.py

ruff check <changed files and agreed broad scope>
ruff format --check <changed files and agreed broad scope>
mypy <changed package paths>
```

## Required Workflow Proof on DB Copy

Use a DB copy only:

```bash
cp <dev_db_path> /tmp/hb_relationship_candidate_proof.sqlite

hb-assistant construction second-brain relationship-candidates scan   --db /tmp/hb_relationship_candidate_proof.sqlite   --as-of <fixed-iso>   --limit 25   --scan-threads 50   --scan-events 50   --dry-run   --summary   --json

# prove zero writes
sqlite3 /tmp/hb_relationship_candidate_proof.sqlite   "SELECT COUNT(*) FROM phase10_relationship_candidates;"

hb-assistant construction second-brain relationship-candidates scan   --db /tmp/hb_relationship_candidate_proof.sqlite   --as-of <fixed-iso>   --apply   --max-persist 5   --summary   --json

# prove capped writes, idempotency, guard columns = 0, no source table mutation
```

## Required Fix Rules

- Fix failures introduced by this package.
- Do not fix unrelated pre-existing failures unless they block proof and Bobby approves the broader touch.
- If broad ruff/mypy surfaces unrelated issues, document them and keep changed files clean.


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

- Relationship tests only pass by weakening guardrails.
- Live proof requires production DB mutation.
- Daily pipeline regression breaks and cannot be fixed locally without large unrelated changes.

## Commit Behavior

Commit expected: yes only if test fixes are made.

Commit message suggestion:

```bash
git commit -m "Harden relationship candidate validation"
```

## Final Response Format

Return:

- all commands run;
- pass/fail status;
- introduced failures fixed;
- pre-existing failures documented;
- DB-copy proof summary;
- commit SHA if applicable.

