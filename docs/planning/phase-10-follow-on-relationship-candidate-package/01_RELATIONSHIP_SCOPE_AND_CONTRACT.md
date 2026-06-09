# 01 — Relationship Scope and Contract

## Objective

Lock the implementation contract for the relationship candidate engine before writing code.

## Scope

Planning and contract only. Do not implement. Do not commit.


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


## Required Contract Decisions

Define and document, based on repo truth:

1. **Relationship types for this slice**
   - Required: `email_calendar` using existing deterministic scorer.
   - Optional only if safe/readiness is proven: `email_procore`, `calendar_procore`, `email_calendar_procore`.
   - Defer Procore relation types if no reliable source-linking/read-model path exists.

2. **Persistence target**
   - Prefer existing `phase10_relationship_candidates` if columns fit.
   - If store helpers are missing, add minimal helper functions.
   - Avoid schema migrations unless the table is genuinely insufficient.

3. **Candidate identity / idempotency**
   - Deterministic relationship id from relationship type + source family/ref pair(s).
   - Unique by relationship type and normalized source refs where repo schema supports it.
   - Re-run must produce `skipped_existing`, not duplicates.

4. **Review state**
   - Default `review_status='pending'` or repo-equivalent.
   - Moderate relationships require review.
   - Strong relationships may be surfaced more prominently but still advisory.

5. **Daily brief integration**
   - Conservative first: bounded relationship context section, e.g. `relationships` in `daily_brief_action_candidates`, or render-time enrichment if persistence table is better suited.
   - Do not make relationship output a substitute for action candidates.
   - Do not persist raw related packet content.

6. **Model use**
   - Relationship determination is deterministic only.
   - Optional model narrative may summarize already-redacted relationship metadata only; default off.
   - No model call required for correctness.

7. **CLI surface**
   - Preferred: `second-brain relationship-candidates scan`.
   - Required flags: `--db`, `--as-of`, `--project-key`, `--limit`, `--scan-threads`, `--scan-events`, `--min-confidence`, `--dry-run`, `--apply`, `--max-persist`, `--summary`, `--json`.
   - Optional: `--include-daily-brief`, `--brief-date`, `--relationship-types`.

## Required Repo Truth Checks

- Confirm `phase10_relationship_candidates` schema.
- Confirm existing store read/write helpers or required additions.
- Confirm current CLI registration pattern.
- Confirm current test conventions.
- Confirm daily pipeline stage pattern if optional integration is considered.

## Deliverable

A short implementation plan in the agent response covering:

- exact files to edit;
- exact tables to read/write;
- exact CLI names/flags;
- exact output JSON schema;
- exact validation commands;
- stop/go decision.

## Stop Conditions

- Relationship table cannot safely store source-linked candidates and a migration would be required but not separately approved.
- Existing scorer is missing or substantially changed.
- Daily pipeline branch has conflicting uncommitted work.

## Commit Behavior

Commit expected: no.

## Final Response Format

Return the locked contract and ask Bobby only if a true stop condition requires approval. Otherwise proceed to Prompt 02.

