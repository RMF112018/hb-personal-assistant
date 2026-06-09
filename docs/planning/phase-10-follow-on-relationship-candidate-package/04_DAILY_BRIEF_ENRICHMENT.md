# 04 — Daily Brief Relationship Enrichment

## Objective

Make relationship candidates visible and useful in the daily brief without overwhelming the operator or persisting raw context.

## Scope

Daily brief read/render enrichment only. No scheduler work. No Obsidian/browser pipeline work beyond normal render compatibility.


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


## Design Requirements

Choose the safest repo-truth-compatible approach:

1. **Preferred:** add a bounded `relationships` section to `daily_brief_action_candidates` via the relationship scan when `--include-daily-brief` is explicitly used.
2. **Alternative:** render-time enrichment from `phase10_relationship_candidates` when no persistence bridge is needed.
3. **Avoid:** duplicating raw relationship packet content in daily brief rows.

## Brief Content Rules

A relationship item should answer:

- what appears related;
- why it appears related, using reason codes, not raw text;
- confidence/class;
- source families involved;
- recommended next operator action: review, prepare meeting, prepare packet, or ignore;
- whether review is required.

Do not include:

- raw email body;
- raw calendar body;
- raw subject if not approved for local-only raw mode;
- join URL;
- email address;
- Procore raw payload;
- prompt or model response.

## Required Tests

- Daily brief default behavior unchanged when no relationship rows exist.
- Relationship section appears when relationship rows exist or when explicit inclusion flag is used.
- Output is deterministic and bounded.
- Section/project filters work if applicable.
- No mutation during render.
- Guard columns stay zero.
- Redaction scan passes for JSON/Markdown/written files.
- Raw local mode, if supported, does not change persisted rows and still refuses repo paths.


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

- Daily brief renderer is being actively modified by Checkpoint 6 local work and conflict risk is high.
- Relationship rows cannot be summarized without raw content.
- The brief becomes noisy or unbounded.

## Commit Behavior

Commit expected: yes, after tests pass.

Commit message suggestion:

```bash
git commit -m "Surface relationship context in daily brief"
```

## Final Response Format

Return:

- enrichment approach selected;
- before/after brief shape;
- tests run and results;
- redaction proof;
- commit SHA.

