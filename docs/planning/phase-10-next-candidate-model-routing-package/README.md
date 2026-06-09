# Phase 10 Next Candidate — Local Model Evaluation + Routing for Daily-Brief Intelligence

## Objective

Implement the next local-agent/model-family candidate after the production-like daily-run pilot: a local-only model evaluation, routing, and daily-brief intelligence quality layer that selects the right local model/profile per task, validates JSON reliability and operator usefulness, and feeds richer source-linked synthesis into the existing daily brief without cloud LLM use or external writeback.

## Operating correction

The production-like daily pipeline pilot and operator runbook are **not** the selected candidate in this package. Treat that work as already in progress or complete. This package implements the next candidate after that loop exists: **local model evaluation + routing for daily-brief intelligence quality**.

## Branch target and safety instructions

Before any work, and again before every commit, run and record:

```bash
cd /Users/bobbyfetting/hb-personal-assistant
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git status --short
git branch --contains HEAD
git rev-parse main
```

Expected posture for this package:
- You are NOT implementing the production-like daily-run pilot. Treat that as already in progress or complete.
- You are implementing the next candidate after that pilot: local model evaluation + routing for daily-brief intelligence quality.
- Work on an experiment branch, recommended: `experiment/local-model-routing-daily-brief-intelligence`.
- If the active branch is `main`, stop before code edits and create/switch to the approved experiment branch.
- If there are uncommitted changes from the in-progress daily-run pilot, stop and report them. Do not overwrite, clean, stash, or commit another agent's work unless Bobby explicitly instructs you.
- Treat local repo truth and DB truth as authoritative over this package.


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


## Expected repo state

Expected, subject to live verification:
- Phase 10 local-agent family exists.
- `second-brain daily-run run` and `second-brain daily-run scheduler {install,status,uninstall}` may already exist or be in progress.
- `daily_brief_action_candidates` is the existing convergence table.
- Local model readiness exists at least as `second-brain local-model status`.
- Available local model families may include `mistral-nemo:12b`, `qwen2.5:14b`, `llama3.1:8b`, and `gpt-oss:20b`, but the local agent must verify actual Ollama availability.
- Current DB schema, migration head, CLI surfaces, and test status must be verified locally before implementation.

## Selected candidate family

**Local model evaluation + routing family**, focused on daily-brief intelligence quality.

This means:
- Add a repeatable local model evaluation harness.
- Evaluate candidate local models against the actual repo tasks: JSON reliability, extraction quality, concise synthesis, source-link preservation, redaction safety, latency, and failure behavior.
- Add a model profile/router layer that chooses a local model/profile per task rather than hardcoding a single model everywhere.
- Add optional advisory daily-brief enrichment that improves operator usefulness without changing external systems and without persisting raw prompt/response content.
- Keep all local-only/no-writeback guardrails intact.

## Why this candidate beats alternatives

- It improves the quality of the current daily-run loop instead of duplicating daily-run scheduling/output work.
- It provides a reusable foundation for later email enrichment, deeper Procore summaries, calendar prep, inbox classification, and relationship candidates.
- It directly addresses the risk that a scheduled brief becomes a sparse dump instead of a useful executive catch-up.
- It can be validated with DB copies, redacted fixtures, and operator-usefulness rubrics before touching any live DB.
- It keeps cloud LLMs and external writeback out of scope.

## Candidate scoring

Candidate scoring after excluding the daily pipeline pilot/operator runbook as in progress:

| Candidate family | ROI | Readiness | Data readiness | Complexity | Safety risk | Time to useful | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Local model evaluation + routing | 9 | 8 | 8 | 5 | 4 | 7 | SELECTED: improves quality across every existing daily-brief stage |
| Email follow-up/raw enrichment | 8 | 7 | 8 | 6 | 7 | 7 | Strong second; should consume model routing once available |
| Calendar deeper meeting prep | 7 | 7 | 7 | 5 | 5 | 7 | Good vertical; less cross-cutting |
| Procore deeper summarization | 7 | 7 | 7 | 5 | 5 | 7 | Good vertical; less cross-cutting |
| Inbox classification/prioritization | 7 | 6 | 8 | 6 | 6 | 6 | Useful, but adds another candidate surface before quality baseline exists |
| Entity normalization/deduplication | 6 | 6 | 7 | 7 | 5 | 5 | Valuable but not immediately visible in the brief |
| Relationship candidate engine | 6 | 6 | 7 | 7 | 5 | 5 | Useful, but repo docs say deterministic scoring already exists |
| File/document parsing/enrichment | 5 | 5 | 3 | 8 | 7 | 4 | Data-blocked until file corpus/read models are present |
| MCP context packet builder | 5 | 5 | 4 | 7 | 8 | 4 | Deferred due raw exposure risk and empty packet table |
| Review/API/dashboard surfacing | 5 | 5 | 6 | 8 | 5 | 4 | Better after quality/routing stabilizes |
| Production/main integration planning | 5 | 6 | 6 | 7 | 6 | 5 | Governance task, not the next local-agent family |
| Obsidian indexing/organization | 4 | 5 | 4 | 6 | 6 | 4 | Lower ROI now; daily-run outputs already cover operator consumption |


## Prompt sequence

| Prompt | Purpose | Expected outputs | Validation required | Commit expected |
|---|---|---|---|---|
| `00_REPO_TRUTH_AND_BRANCH_GUARD.md` | Verify branch, HEAD, dirty tree, schema, current daily-run status, and candidate exclusion | Repo-truth memo, no code changes | Git/status/schema/CLI probes | No |
| `01_CANDIDATE_SELECTION_AND_SCOPE_LOCK.md` | Confirm selected candidate and implementation boundaries from live repo truth | Scope lock and file/table/CLI map | Read-only repo/DB audit | Yes, docs-only if useful |
| `02_MODEL_EVAL_HARNESS_AND_FIXTURE_CONTRACTS.md` | Build local model eval harness and safe fixture contracts | Eval library, fixtures, tests | Unit + CLI dry-run + redaction checks | Yes |
| `03_MODEL_PROFILE_ROUTER_AND_CONFIG.md` | Implement model profile registry/router and fallback behavior | Config, router, status surface | Unit + CLI + no-cloud proof | Yes |
| `04_DAILY_BRIEF_INTELLIGENCE_ADAPTERS.md` | Add optional advisory synthesis/enrichment using router | Daily-brief enrichment layer | DB-copy dry-run/apply proof, usefulness rubric | Yes |
| `05_CLI_OPERATOR_AND_REPORTING_SURFACES.md` | Add operator CLI surfaces for eval, routing, and brief-quality reporting | CLI commands + JSON outputs | CLI tests + structured output validation | Yes |
| `06_TESTS_AND_VALIDATION.md` | Expand tests and regression coverage | Green targeted suites | ruff/format/mypy/targeted pytest | Yes |
| `07_LIVE_WORKFLOW_PROOF.md` | Prove actual behavior on DB copy/temp paths | Redacted evidence bundle | Workflow and agent-output proof | Yes, evidence only |
| `08_DOCS_EVIDENCE_AND_RUNBOOK.md` | Update architecture docs and runbook | Docs/runbook/evidence index | Docs lint/manual review | Yes |
| `09_FINAL_AUDIT_AND_HANDOFF.md` | Conduct final repo-truth audit and handoff | Final handoff, acceptance matrix | Full scoped validation | No unless fixes are required |

## Full implementation acceptance criteria

See `ACCEPTANCE_CRITERIA.md`.

## Stop conditions

See `STOP_CONDITIONS.md`.

## Rollback instructions

- Every prompt that changes code must commit independently with a clear commit message.
- Rollback is by reverting the prompt-specific commits in reverse order.
- Schema migrations, if any, must be additive and reversible by abandoning the experiment branch unless Bobby explicitly approves destructive rollback work.
- No live production DB mutation should be needed. If the implementation requires it, stop.

## Evidence expectations

Evidence must be redacted and command-output focused:
- Branch/HEAD/tree state.
- Schema and migration head.
- Model availability and selected profiles, but no raw prompts or responses.
- Eval metrics: JSON-valid rate, schema-valid rate, refusal/fail rate, latency, redaction findings, usefulness scores.
- CLI receipts and DB-copy row counts.
- Guard-column sums and no-writeback proof.
- Daily-brief before/after quality comparison using redacted or local-only safe artifacts.

## Final handoff format

The local agent final response must include:
- Branch and HEAD.
- Commit list.
- Files changed.
- Schema/migration status.
- CLI surfaces added/changed.
- Tests run and results.
- Live workflow proof summary.
- Guardrail proof summary.
- Caveats/pre-existing failures.
- Exact next recommended candidate after this work.
