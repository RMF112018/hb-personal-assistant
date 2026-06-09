# Phase 10 Follow-On Package — Relationship Candidate Engine

## Objective

Implement the best next local-agent/model-family candidate **after** the production-like daily pipeline pilot: a deterministic-first, local-only **relationship candidate engine** that links existing email, calendar, and, where repo truth supports it, Procore context into reviewable relationship candidates and daily-brief enrichment.

This package is intentionally **not** a daily pipeline/scheduler package. It assumes the daily pipeline pilot is already in progress or complete and focuses on the highest-ROI follow-on: making the brief smarter by connecting the already-ingested signals rather than adding another disconnected surface.

## Why This Candidate

The current Phase 10 branch already proves:

- email extraction → review → promotion → follow-up watch;
- Procore action-signal digest;
- calendar meeting-prep candidates;
- daily-brief convergence through `daily_brief_action_candidates`;
- daily-brief render and `--raw` local-consumption mode;
- pipeline orchestration through `second-brain pipeline run`.

Once that pipeline is scheduled, the next gap is **context linkage**. The system can tell Bobby about emails, Procore signals, and meetings, but it does not yet operationalize relationships across those sources as a first-class scan/apply workflow. The repo already contains strong substrate for this candidate: `phase10_relationship_candidates`, deterministic `relationship_scoring.py`, and `related_context_action_packet` / `triage_batch_packet` builders. This package turns that substrate into a production-like local-agent family.

## Target Repo / Branch

- Repository: `RMF112018/hb-personal-assistant`
- Target branch: `experiment/local-agent-family-proof`
- Working directory: `/Users/bobbyfetting/hb-personal-assistant`

## Required First Command

Before doing any audit or implementation work, run:

```bash
cd /Users/bobbyfetting/hb-personal-assistant

git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git status --short
git branch --contains HEAD
git rev-parse main
```

Expected:

- branch is `experiment/local-agent-family-proof`, unless Bobby explicitly says otherwise;
- working tree is clean unless explicitly explained;
- current work is contained where Bobby expects it;
- `main` is not modified by this prompt sequence.

If this check fails, stop and report the exact branch/HEAD/tree state. Do not continue until corrected.


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


## Local Agent Execution Instructions

Execute the prompt files in numeric order. After each prompt:

1. Re-check branch/HEAD/tree.
2. Run required validation for that prompt.
3. Commit only when the prompt explicitly says `Commit expected: yes`.
4. Do not continue after a true stop condition.
5. Treat repo truth and DB truth as authoritative over package assumptions.
6. Keep evidence command-output focused and redacted.
7. Avoid large, speculative rewrites. Prefer additive, narrowly scoped implementation.

## Prompt Sequence

| Prompt | Purpose | Expected outputs | Validation required | Commit expected |
|---|---|---|---|---|
| `00_REPO_TRUTH_AND_BRANCH_GUARD.md` | Verify branch, audit current Phase 10/daily-pipeline state, and confirm this follow-on is still the correct next candidate | Audit memo, scope risks, no code changes | Branch/git proof, code/doc/schema inspection | No |
| `01_RELATIONSHIP_SCOPE_AND_CONTRACT.md` | Lock the exact relationship-candidate contract, table/write plan, CLI names, and integration boundaries | Implementation plan, contract notes, stop/go checklist | Schema/table inspection, existing scorer/packet audit | No |
| `02_CORE_RELATIONSHIP_ENGINE.md` | Implement deterministic scan/build layer using existing relationship scorer and bounded packet builders | Core module/store writer/readers, dry-run report | Unit tests, no raw egress tests | Yes |
| `03_CLI_AND_PIPELINE_INTEGRATION.md` | Add `second-brain relationship-candidates scan` and optional daily-pipeline stage integration without disrupting current pipeline | CLI surface, JSON output, optional pipeline hook | CLI tests, dry-run/apply cap tests, pipeline regression | Yes |
| `04_DAILY_BRIEF_ENRICHMENT.md` | Surface relationship context in daily brief without raw persistence and without making the brief noisy | Brief section/enrichment rules, render support | Render tests, no mutation tests, operator usefulness checks | Yes |
| `05_TESTS_AND_VALIDATION.md` | Harden regression coverage and run code/workflow/agent-output validation | Passing target suites, documented pre-existing failures | ruff/format/mypy, checkpoint regressions, DB-copy live proof | Yes, only if fixes made |
| `06_LIVE_WORKFLOW_PROOF.md` | Prove end-to-end behavior on a DB copy with real local data | Redacted evidence outputs and row-count proof | Dry-run/apply/idempotency/fail-closed/status proof | No, unless evidence docs are intentionally committed in next prompt |
| `07_DOCS_EVIDENCE_AND_RUNBOOK.md` | Update architecture/evidence/runbook with redacted command outputs | Docs/evidence/runbook updates | Documentation consistency and redaction scan | Yes |
| `08_FINAL_AUDIT_AND_HANDOFF.md` | Conduct final repo-truth audit and prepare final handoff | Completion audit, risk register, validation matrix | Full branch/git/status/test proof | No, unless handoff doc is explicitly committed |

## Full Implementation Acceptance Criteria

The implementation is complete only when all of the following are true:

- `second-brain relationship-candidates scan` exists, defaults to dry-run, and emits structured JSON.
- Dry-run writes zero rows.
- Apply mode requires an explicit cap and fails closed without it.
- Apply mode persists only reviewable, source-linked relationship candidates to `phase10_relationship_candidates` or the repo-truth equivalent table.
- Persisted rows are idempotent and all Phase 10 guard columns remain zero.
- Relationship candidates are deterministic-first; any local-model narrative is optional, bounded, local-only, redacted-input-only, and never required for correctness.
- Email↔calendar relationship scoring reuses or composes the existing deterministic scorer instead of allowing a model to decide relatedness.
- Procore relationship support is included only if repo/DB truth shows a safe source-linking path; otherwise it is explicitly deferred with a documented reason.
- Daily brief integration is useful but conservative: source-linked relationship context appears as either a dedicated section or bounded annotations without overwhelming the main action list.
- The existing daily pipeline remains stable and regression-tested.
- No email/calendar/Procore/Graph/external writeback exists.
- No raw content is committed to repo/evidence/logs/tests.
- Live proof runs only on a DB copy or temp DB unless Bobby separately approves production mutation.
- Docs and evidence explain stop conditions, rollback, and operational use.

## Stop Conditions

See `STOP_CONDITIONS.md`. In general, stop immediately if branch/git state is wrong, daily pipeline work is actively conflicting, schema/table assumptions are false, raw data would need to be committed, a production DB would be mutated without approval, or the relationship candidate contract cannot be satisfied safely.

## Rollback Instructions

- Keep implementation additive.
- Each committed prompt should be revertible independently.
- Schema changes are strongly discouraged unless repo truth proves V41/V43 tables are insufficient; any migration must be additive and separately justified.
- If a commit breaks Checkpoint 1-current behavior, revert the latest commit before continuing.
- If live proof writes incorrect rows to a DB copy, discard the DB copy and fix code before any further apply test.

## Evidence Expectations

Evidence must be redacted and command-output focused:

- branch/HEAD/tree proof;
- schema status proof;
- CLI JSON proof;
- dry-run zero-write proof;
- apply capped/idempotent proof;
- guard-column sum proof;
- daily brief output shape proof without raw content;
- tests/ruff/format/mypy results;
- explicit list of unrelated/pre-existing failures.

## Final Handoff Format

The local agent final response must include:

- branch and HEAD;
- commits made;
- files changed;
- schema changes, if any;
- CLI surfaces added/changed;
- validation commands and results;
- live workflow proof summary;
- guardrail proof summary;
- daily pipeline regression proof;
- caveats / stop conditions encountered;
- exact next recommended step.

