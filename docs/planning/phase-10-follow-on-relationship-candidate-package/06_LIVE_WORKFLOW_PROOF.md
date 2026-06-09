# 06 — Live Workflow Proof

## Objective

Prove the relationship candidate engine end-to-end on real local data using only a DB copy or safe temp path.

## Scope

Validation/evidence only. Do not change code unless a true defect is found; if so, fix, re-test, and document.


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


## Required Proofs

1. **Branch proof**
   - branch;
   - HEAD;
   - dirty tree;
   - branch containment;
   - main HEAD.

2. **DB-copy proof**
   - source DB path redacted if necessary;
   - copy DB path under `/tmp`;
   - schema version;
   - relevant table row counts before/after.

3. **Dry-run proof**
   - scan command;
   - relationships considered;
   - would-persist count;
   - persisted = 0;
   - relationship table unchanged.

4. **Apply capped proof**
   - apply command with cap;
   - persisted <= cap;
   - skipped count visible;
   - source tables unchanged.

5. **Idempotency proof**
   - re-run same command;
   - persisted = 0 or skipped_existing accounts for prior rows.

6. **Guardrail proof**
   - all Phase 10 guard columns sum to 0 for new relationship rows and any brief rows produced.

7. **Redaction proof**
   - scan output contains no URL, join URL, raw email address, raw HTML, token, raw prompt, raw response, signed/download URL, or body payload.

8. **Daily brief proof**
   - if brief integration exists, render a brief on DB copy;
   - prove relationship context appears and remains bounded/redacted;
   - prove render does not mutate rows.

9. **Pipeline regression proof**
   - run existing `second-brain pipeline run` dry-run on DB copy;
   - prove it still completes or fails only for documented pre-existing reasons.

## Evidence Handling

- Do not paste raw titles, raw bodies, join URLs, emails, or tokens into evidence.
- Use counts, booleans, reason codes, section names, and redaction scan results.
- Evidence can be staged for the docs prompt but should not be committed here unless explicitly scoped.

## Stop Conditions

- Any raw private content appears in stdout/logs/evidence.
- Guard columns nonzero.
- Source tables mutate unexpectedly.
- Production DB path is targeted by apply mode without explicit Bobby approval.

## Commit Behavior

Commit expected: no, unless a defect fix was required and validated.

## Final Response Format

Return a live proof summary with command blocks and redacted outputs sufficient for Bobby to trust end-to-end behavior.

