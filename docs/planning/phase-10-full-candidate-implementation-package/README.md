# Phase 10 Full Candidate Implementation Package

Package generated: 2026-06-09  
Repository: `RMF112018/hb-personal-assistant`  
Repo-local package target path: `docs/planning/phase-10-full-candidate-implementation-package`  
Baseline proven by Bobby before package generation:

```text
branch: main
HEAD: 0c75f4a77b5987cdbd2a058504f5423d69d225f1
main: 0c75f4a77b5987cdbd2a058504f5423d69d225f1
origin/main: 0c75f4a77b5987cdbd2a058504f5423d69d225f1
git status --short: clean
```

## Objective

Implement every Phase 10 candidate identified by the prior repo-truth audit, in a controlled sequence, on a single implementation branch, with one evidence-backed checkpoint per candidate and a final integration audit.

The candidates are:

1. Daily Brief Surface Convergence
2. Candidate Review UX
3. Follow-up Watch Quality
4. Scheduler / Daily-Run Reliability
5. Local Model Routing Refinement
6. Procore Expansion
7. Relationship / Entity Normalization
8. MCP Context Packet Hardening
9. Document / File Parsing
10. Final Integration Audit and Handoff

This package is intended to be executable in one shot by Bobby's local code agent with:

```text
Execute the objective defined at docs/planning/phase-10-full-candidate-implementation-package/README.md
```

## Required execution cadence

Execute the prompts in numeric order from `prompts/`.

After completing, validating, evidencing, and committing each prompt, wait exactly 10 minutes before starting the next prompt.

Use either a literal shell pause:

```bash
sleep 600
```

or an equivalent 10-minute execution pause enforced by the local agent runtime.

Do not batch prompts together. Do not skip the pause. The pause is part of the execution contract and gives filesystem, local model, DB, scheduler, and evidence artifacts time to settle between checkpoints.

## Branching contract

Before implementing anything:

```bash
cd /Users/bobbyfetting/hb-personal-assistant
git fetch origin
git checkout main
git pull --ff-only origin main
git status --short
git rev-parse HEAD
git rev-parse origin/main
```

Expected clean baseline at package creation was `0c75f4a77b5987cdbd2a058504f5423d69d225f1`. If `main` has advanced, continue only if the tree is clean and `main == origin/main`; record the new baseline in the evidence. Do not require Bobby to re-authorize if this is a normal fast-forward.

Create one branch:

```bash
git checkout -b experiment/phase-10-full-candidate-implementation
```

If the branch already exists, inspect it before continuing. Do not overwrite prior work. Prefer creating a timestamped branch only if the existing branch contains unrelated work.

## Commit contract

Each candidate prompt must produce one focused commit unless the prompt explicitly discovers that a repo-truth split is required. Commit messages should use this pattern:

```text
feat(second-brain): implement phase 10 <candidate-slug>
```

or, for hardening-only candidates:

```text
fix(second-brain): harden phase 10 <candidate-slug>
```

The final audit prompt should produce either:

```text
docs(second-brain): add phase 10 full candidate handoff
```

or no commit if no files changed.

Do not commit secrets, local configuration, production DB files, generated browser files containing raw/sensitive content, or non-redacted evidence.

## Universal guardrails

These apply to every prompt.

### Safety and privacy

Do not persist, log, commit, or place in evidence any of the following:

- raw email bodies
- raw model prompts
- raw model responses
- full HTML bodies from Graph, email, calendar, Procore, SharePoint, or document sources
- signed URLs
- download URLs
- join links
- bearer tokens
- refresh tokens
- cookies
- API keys
- secrets
- passwords
- private email-address dumps
- attendee arrays
- document text containing sensitive project or personal content, unless deliberately bounded, sanitized, and review-safe

Use hashes, counts, short type labels, IDs, redaction booleans, and synthetic fixtures for proof whenever feasible.

### Writeback boundaries

No external writeback is allowed unless an existing repo feature already supports an internal local write and the prompt explicitly needs it.

Forbidden without Bobby's explicit separate approval:

- sending or drafting emails
- mutating calendars
- creating, updating, or deleting Procore resources
- writing to Microsoft Graph / SharePoint / OneDrive
- writing to MCP-connected external stores
- posting to Slack/Teams or other external systems
- uploading generated evidence externally

### DB rules

- Validate migrations on temporary DB copies first.
- Do not mutate Bobby's production DB during validation except through an explicitly existing local apply workflow that is already designed to mutate the local app DB.
- If a candidate needs persisted local state, prefer a schema migration only when repository truth shows no suitable table exists.
- Each prompt must include a guard-column proof where applicable.
- Each prompt must prove production DB unchanged unless the candidate intentionally uses an apply path against a disposable test DB.

### Local model rules

- Local model only.
- No cloud LLM fallback.
- Model unavailable must fail closed or degrade deterministically.
- No raw prompt/response persistence.
- Preserve source links and candidate IDs.
- Every model-assisted output must be review-safe and cite its local source IDs.

### Final output evidence

Each candidate must generate evidence that includes what is intended as the final user/operator output for that candidate.

Examples:

- Daily Brief Surface Convergence: browser HTML, Obsidian markdown, redacted status JSON, and pending follow-up section proof.
- Candidate Review UX: CLI transcript, JSON/Markdown review output, accepted/rejected action preview.
- Follow-up Watch Quality: watch report, pending follow-up report, stale/closed/open-loop proof.
- Scheduler Reliability: scheduler install preview/status, launchd/run status file, degraded/failure status proof.
- Local Model Routing: routing report, eval result summary, fail-closed proof.
- Procore Expansion: Procore digest/monitoring read model output and source-refresh/sync proof using safe data.
- Relationship / Entity Normalization: review-safe candidate report and dedupe/alias proof.
- MCP Context Packet: generated packet proof and final MCP-safe packet artifact.
- Document / File Parsing: parsed document/file index output using synthetic or sanitized fixture files; final extraction/read-model proof.
- Final Integration Audit: final handoff, evidence index, test matrix, and operator runbook.

## Evidence root

Use this root:

```text
docs/evidence/phase-10-full-candidate-implementation/
```

Each candidate must write to a numbered subdirectory:

```text
docs/evidence/phase-10-full-candidate-implementation/01-daily-brief-surface-convergence/
docs/evidence/phase-10-full-candidate-implementation/02-candidate-review-ux/
docs/evidence/phase-10-full-candidate-implementation/03-followup-watch-quality/
docs/evidence/phase-10-full-candidate-implementation/04-scheduler-daily-run-reliability/
docs/evidence/phase-10-full-candidate-implementation/05-local-model-routing-refinement/
docs/evidence/phase-10-full-candidate-implementation/06-procore-expansion/
docs/evidence/phase-10-full-candidate-implementation/07-relationship-entity-normalization/
docs/evidence/phase-10-full-candidate-implementation/08-mcp-context-packet-hardening/
docs/evidence/phase-10-full-candidate-implementation/09-document-file-parsing/
docs/evidence/phase-10-full-candidate-implementation/10-final-integration-audit/
```

Every evidence subdirectory must include:

- `README.md`
- `branch-state.txt`
- `changed-files.txt`
- `validation-commands.txt`
- `validation-results.md`
- `final-output-manifest.md`
- `safety-scan-results.txt`
- candidate-specific evidence files named by the prompt

Use `templates/evidence_manifest_template.md`, `templates/final_output_manifest_template.md`, and `templates/validation_matrix_template.md`.

## Required prompt sequence

Run these in order:

1. `prompts/01_daily_brief_surface_convergence.md`
2. wait 10 minutes
3. `prompts/02_candidate_review_ux.md`
4. wait 10 minutes
5. `prompts/03_followup_watch_quality.md`
6. wait 10 minutes
7. `prompts/04_scheduler_daily_run_reliability.md`
8. wait 10 minutes
9. `prompts/05_local_model_routing_refinement.md`
10. wait 10 minutes
11. `prompts/06_procore_expansion.md`
12. wait 10 minutes
13. `prompts/07_relationship_entity_normalization.md`
14. wait 10 minutes
15. `prompts/08_mcp_context_packet_hardening.md`
16. wait 10 minutes
17. `prompts/09_document_file_parsing.md`
18. wait 10 minutes
19. `prompts/10_final_integration_audit.md`

## Global validation expectation

At the end of every prompt, run the narrowest relevant tests first, then broader validation as practical. At minimum, each prompt must run:

```bash
git status --short
python -m compileall src tests
```

Then run targeted `pytest` and `ruff`/`mypy` commands relevant to changed files if those tools are configured in the repo.

If broad validation exposes unrelated pre-existing failures, do not fix unrelated files by default. Record the failure, prove whether your changed files are clean, and continue only if the candidate is locally validated.

## Global stop conditions

Stop and produce a clear handoff if any of these occur:

1. The tracked tree is dirty before starting a prompt and the changes are not from the prior prompt.
2. The branch is not the intended implementation branch.
3. A required migration cannot be validated on a temporary DB copy.
4. Any raw body/prompt/response/URL/token/secret/email dump appears in evidence, committed files, logs, status, browser output, Obsidian output, or JSON output.
5. Any guard column or forbidden-writeback counter becomes nonzero.
6. Production DB checksum changes unexpectedly.
7. The local model route attempts cloud fallback.
8. The implementation sends/drafts email, mutates calendar, writes to Procore, writes to Graph, or writes to MCP/external systems.
9. A final operator-facing output presents unreviewed model inference as accepted fact.
10. A candidate cannot produce its required final-output evidence.

## Final deliverable

After Prompt 10, produce a final handoff summarizing:

- branch name and final HEAD
- baseline SHA and final SHA
- all commits
- all changed files grouped by candidate
- all evidence directories
- all final output artifacts
- validation pass/fail matrix
- known limitations
- merge recommendation
- exact commands Bobby can run to manually verify
