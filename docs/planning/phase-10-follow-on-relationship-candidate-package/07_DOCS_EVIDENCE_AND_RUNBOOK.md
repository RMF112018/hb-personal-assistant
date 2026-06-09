# 07 — Docs, Evidence, and Runbook

## Objective

Update architecture, evidence, and operator runbook documentation for the relationship candidate engine using only redacted, command-output-focused proof.

## Scope

Docs/evidence/runbook only unless a minor code-doc mismatch requires a small fix.


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

- New architecture note, e.g. `docs/architecture/233-phase-10-relationship-candidate-engine.md`
- Update `docs/architecture/232-phase-10-local-agent-family.md` only if appropriate
- Update or add evidence under `docs/evidence/phase-10-local-agent-family/`
- Update runbook/status docs if repo already has a Phase 10 runbook

## Documentation Requirements

Document:

- purpose and relationship to daily pipeline;
- why this follows the daily pipeline rather than replacing it;
- CLI usage;
- dry-run/apply/cap behavior;
- relationship types implemented and deferred;
- persistence tables and idempotency;
- daily brief integration;
- guardrails;
- validation commands and outcomes;
- live proof summary;
- known pre-existing failures;
- rollback path.

## Evidence Requirements

Evidence must include:

- branch/HEAD/tree proof;
- schema readiness;
- dry-run zero-write proof;
- apply capped proof;
- idempotency proof;
- guard columns zero;
- redaction scan;
- daily brief proof if integrated;
- no external writeback proof;
- tests/ruff/format/mypy summary.

Evidence must not include raw private data.

## Stop Conditions

- Evidence would require committing raw data.
- Docs contradict live repo behavior.
- Existing docs reveal that the same feature already exists and this work duplicated it.

## Commit Behavior

Commit expected: yes, after docs/evidence are redaction-checked.

Commit message suggestion:

```bash
git commit -m "Document Phase 10 relationship candidate engine"
```

## Final Response Format

Return:

- docs/evidence files changed;
- redaction scan method;
- validation summary;
- commit SHA.

