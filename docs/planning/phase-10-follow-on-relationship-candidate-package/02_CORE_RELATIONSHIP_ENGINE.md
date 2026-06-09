# 02 — Core Relationship Engine

## Objective

Implement the deterministic core relationship-candidate scan/build layer using existing scoring and packet infrastructure.

## Scope

Additive code only. No CLI registration yet unless needed for tests. No daily pipeline integration yet.


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

- `src/hb_assistant/construction/second_brain/local_ai/relationship_scoring.py`
- New candidate module, likely `src/hb_assistant/construction/second_brain/local_ai/relationship_candidates.py`
- `src/hb_assistant/construction/store.py` or relevant store module/helper files
- Existing test area under `tests/`

## Implementation Requirements

1. Build a core function such as `build_relationship_candidates(...)` that:
   - accepts `store`, `now_utc`, `project_key`, `limit`, `scan_threads`, `scan_events`, `min_confidence`, `dry_run`, `max_persist`;
   - uses the existing deterministic `find_email_calendar_relationships` or composes `score_email_calendar_relationship` directly;
   - returns structured JSON with `ok`, `applied`, `summary`, `relationships`, `guardrails`;
   - writes nothing in dry-run;
   - fails closed if `dry_run=False` and `max_persist` is absent;
   - caps actual persisted rows;
   - skips missing source refs;
   - is idempotent.

2. Persist relationship candidates to the repo-truth relationship table:
   - use only redacted/hash/source-ref fields;
   - include relationship type/class/confidence/reason codes/score components if schema allows;
   - include review-required marker if schema allows;
   - do not persist raw packet content, raw subjects, raw bodies, join URLs, emails, prompts, or responses.

3. Add minimal store helpers:
   - list bounded source inputs if not already available;
   - insert/upsert relationship candidate;
   - list existing candidate ids for idempotency;
   - guard-column validation helper only if useful for tests.

4. Keep model optional and off:
   - no model call in core relationship determination;
   - if optional narrative is added, it must consume only relationship metadata and be excluded from persistence unless redacted and schema-approved.

## Required Tests

Add targeted tests covering:

- deterministic scoring reused, not model-decided;
- dry-run zero writes;
- apply requires cap;
- cap bounds persisted rows;
- idempotent re-run;
- skips missing source refs;
- moderate relationships review-required;
- weak relationships excluded by default;
- guard columns stay zero;
- no raw content / URL / email / HTML in persisted rows or JSON output;
- empty input returns valid empty report.


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

- Store schema cannot safely persist source-linked relationship candidates without migration.
- Tests show existing scorer emits raw content.
- Implementation requires mutating email/calendar/Procore source tables.

## Commit Behavior

Commit expected: yes, after tests pass.

Commit message suggestion:

```bash
git commit -m "Add Phase 10 relationship candidate core"
```

## Final Response Format

Return:

- files changed;
- core API shape;
- table writes;
- tests run and results;
- guardrail proof;
- commit SHA.

