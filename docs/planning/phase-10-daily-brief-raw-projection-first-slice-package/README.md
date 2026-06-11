# Phase 10 — Daily Brief Raw Projection First Slice Implementation Package

Repository: `RMF112018/hb-personal-assistant`  
Local repo path: `/Users/bobbyfetting/hb-personal-assistant`  
Target branch: `experiment/phase-10-daily-brief-raw-projection-first-slice`  
Package path once copied into repo: `docs/planning/phase-10-daily-brief-raw-projection-first-slice-package/README.md`  
Evidence root: `docs/evidence/phase-10-daily-brief-raw-projection-first-slice`  
Commit basis to audit against first: `4d8ca0717324955dab539ebf0690b5a93d4db6e0`

## Objective

Implement the first daily-brief usefulness slice identified by the raw-projection follow-up audit.

This slice turns the newly available raw/structured substrate into a source-linked, operator-useful daily brief by implementing and validating:

1. **V49 email/calendar structured projection activation**
   - Make V49 raw → structured projection run from an explicit, safe daily-run/local pipeline stage.
   - Preserve the existing CLI safety contract: dry-run default, no live Graph calls, no external writeback, no raw value emission.
   - Persist projection receipts and coverage receipts when applied.
   - Treat projection unmapped-fields failures as degraded/blocked states, not silent success.

2. **Source-linked calendar and Procore daily-brief candidate persistence**
   - Calendar prep must persist source-linked `daily_brief_action_candidates` when useful calendar source rows exist.
   - Procore digest must persist ranked, source-linked candidates from promoted signals and suppress aggregate sludge into diagnostics/backlog.
   - Candidate writes must route through the central `daily_brief_candidate_writer.persist_candidate_with_refs` contract.
   - Candidate source-ref coverage must be 100% for executive/top-priority sections.

3. **Project identity/project-key resolution first pass**
   - Use existing project alias/config/source-location truth to improve project assignment without unsafe automation.
   - Persist review-safe project identity/match/promotion artifacts into existing tables where available.
   - Do not invent project mappings. Unknown or ambiguous mappings must become `Needs Project Review` / `__needs_review__` with clear reason codes.

4. **Hard usefulness, source-ref, and contradiction gates**
   - A daily brief must not report clean success when useful source data exists but daily candidates are empty.
   - If raw/structured calendar or Procore source data exists and the candidate projection stage yields zero rows, mark the run degraded or failed with a precise reason.
   - Source-ref coverage for executive sections must be a success gate.
   - Empty email/follow-up/task/commitment layers must produce data-gap cards rather than silent omissions.

5. **Operator surfaces and proof**
   - Add or harden CLI/status surfaces that show projection status, candidate counts, source-ref coverage, project-key coverage, suppressed Procore backlog, data gaps, and usefulness verdict.
   - Generate a raw-free evidence bundle from DB-copy validation.
   - Do not mutate the production DB during validation.

The implementation is code + tests + docs + evidence. It is not an audit-only task.

## Required branch

```bash
cd /Users/bobbyfetting/hb-personal-assistant
git fetch origin
git checkout main
git pull --ff-only
git checkout -b experiment/phase-10-daily-brief-raw-projection-first-slice
```

If the branch already exists, inspect it. Do not reset, force-push, merge, or rebase without explicit operator approval.

## Baseline evidence from the follow-up audit

The attached DB/audit found:

| Area | Baseline finding |
|---|---|
| Schema | V49 present; V46/V47/V48/V49 migrations applied |
| Email raw | `email_message_raw_content = 405`; `email_thread_raw_context = 223` |
| Calendar raw | `calendar_event_raw_content = 138`; near-term raw events = 44 |
| Email/calendar structured | `email_raw_message_structured = 0`; `calendar_raw_event_structured = 0` |
| Projection receipts | `email_calendar_projection_runs = 0`; `email_calendar_projection_coverage = 0` |
| Raw access audit | `raw_content_access_events = 525` |
| Procore raw | `procore_endpoint_raw_payloads = 40,245`; `live_full_payload = 10,325` |
| Procore action signals | `procore_action_signals = 5,912` |
| Daily candidates | `daily_brief_action_candidates = 0`; `candidate_source_refs = 0` |
| Project identity | `construction_project_identity = 0`; keyword registry/source matches empty |
| Follow-up/task layers | `follow_up_watch_items = 0`; `task_candidates = 0`; `commitment_candidates = 0`; `email_followup_enrichments = 0` |

This package must verify current repo/DB truth first because the local repo may have advanced since the audit.

## Scope lock

### In scope

- V49 projection activation service/stage.
- Daily-run orchestration integration for projection and candidate stages.
- Calendar candidate projection into `daily_brief_action_candidates` with `candidate_source_refs`.
- Procore ranked candidate projection into `daily_brief_action_candidates` with `candidate_source_refs`.
- Suppressed Procore aggregate backlog diagnostics.
- Project identity/project-key resolution first pass and review-safe promotion/match surfaces.
- Source-ref gate hardening.
- Usefulness/contradiction gate hardening.
- Empty email/follow-up/task data-gap cards.
- CLI/status JSON/operator surfaces.
- Tests, DB-copy validation, evidence, docs, runbook, final audit.

### Non-goals

- No cloud LLM use.
- No external writeback.
- No Procore writeback.
- No Microsoft Graph writeback.
- No calendar mutation.
- No email send/draft/archive/delete/label mutation.
- No production DB mutation during validation.
- No destructive migration.
- No raw private content in repo files, evidence, test fixtures, status files, logs, committed docs, or screenshots.
- No copying raw bodies, prompts, model responses, join URLs, signed/download URLs, tokens, secrets, cookies, or private payloads into artifacts.
- Do not implement a full semantic email follow-up extraction agent in this slice; only readiness/data-gap surfaces unless needed to satisfy source-linked candidate gates safely.

## Mandatory behavior decisions

These decisions are made. Do not re-ask them.

1. **Structured projections become the preferred substrate.** Local agents/read models should prefer V49 structured email/calendar rows over raw landing and legacy metadata when available.
2. **Projection is required before candidate projection.** Candidate generation should run after projection status is known.
3. **Daily candidates are the model/context substrate.** The daily brief must not rely on ad hoc unpersisted source rows for executive action sections.
4. **Source refs are mandatory.** Candidate rows without source refs are not model-supported and cannot produce clean success.
5. **Procore aggregate sludge is diagnostic only.** Suppressed backlog can be shown in data-quality/backlog diagnostics, not as executive action rows.
6. **Unknown projects are review items.** Do not fabricate project keys. Ambiguous calendar/email/project mappings become `Needs Project Review` with reason codes.
7. **Useful source data + zero candidates is a contradiction.** This must degrade/fail the brief with a clear reason.
8. **Validation uses DB copies.** Production DB hash/size/mtime must be unchanged during validation.

## Required implementation order

Execute the prompt files in `prompts/` in numeric order. Do not skip a prompt. Each prompt has acceptance criteria and evidence requirements.

| Prompt | Purpose |
|---|---|
| 00 | Repo-truth, branch, and baseline preflight |
| 01 | Unified design contract and current code map |
| 02 | DB-copy baseline, schema, and safe SQL inventory |
| 03 | V49 projection activation service/stage |
| 04 | Daily-run projection integration and receipts |
| 05 | Calendar candidate projection and project-resolution first pass |
| 06 | Procore ranked candidate projection and aggregate suppression |
| 07 | Project identity registry/review-safe promotion flow |
| 08 | Source-ref, evidence, and usefulness contradiction gates |
| 09 | Daily brief orchestration, status, and data-gap cards |
| 10 | Email/follow-up readiness surfaces without overbuilding |
| 11 | CLI/operator surfaces and runbook commands |
| 12 | Test suite and static validation |
| 13 | DB-copy live proof and evidence generation |
| 14 | Docs, architecture note, and operator runbook |
| 15 | Final integration audit and residual-work elimination |

## Required evidence files

Create these under `docs/evidence/phase-10-daily-brief-raw-projection-first-slice/`:

```text
00-repo-state.md
01-branch-state.txt
02-target-commit-basis.md
03-db-copy-baseline.json
04-schema-and-migrations.json
05-table-counts-baseline.json
06-v49-projection-dry-run.json
07-v49-projection-apply-copy.json
08-v49-projection-coverage-after.json
09-calendar-candidate-dry-run.json
10-calendar-candidate-apply-copy.json
11-procore-digest-dry-run.json
12-procore-digest-apply-copy.json
13-project-identity-resolution-proof.json
14-candidate-source-ref-coverage.json
15-usefulness-gate-proof.json
16-contradiction-known-bad-proof.json
17-daily-run-integrated-copy-proof.json
18-status-json-proof.json
19-cli-help-snapshots.md
20-no-raw-leak-scan.txt
21-guard-column-proof.json
22-no-writeback-proof.md
23-production-db-unchanged-proof.txt
24-validation-results.md
25-usefulness-scorecard.md
26-known-limitations.md
27-final-handoff.md
28-residual-work-audit.md
```

Evidence must contain counts, statuses, hashes, table/column names, source-family names, and reason codes only. Do not include raw values.

## Acceptance criteria

All must be true:

- V49 email/calendar projection can be run safely against a DB copy and produces structured rows when raw rows exist.
- `email_calendar_projection_runs` and `email_calendar_projection_coverage` are populated in apply-copy proof.
- Projection coverage reports zero unmapped primary/nested business fields for families with raw rows.
- Calendar candidate projection persists source-linked candidates when in-window useful events exist.
- Procore digest persists source-linked candidates from promoted ranked signals when actionable signals exist.
- Suppressed Procore backlog is diagnostic only and does not become executive action rows.
- `candidate_source_refs` coverage is 100% for executive sections written by this slice.
- Project-key coverage improves where deterministic/project-alias evidence exists; unresolved mappings are review-safe and explicit.
- Daily-run/status surfaces show projection counts, candidate counts, source-ref coverage, project-key coverage, suppressed backlog count, data gaps, and usefulness verdict.
- A known-bad condition where source rows exist but candidates are empty cannot return clean success.
- Empty email/follow-up/task layers are surfaced as data gaps, not silent “nothing to do.”
- Production DB hash/size/mtime are unchanged during validation.
- No external writeback occurs.
- Guard columns remain zero.
- No raw leak scan passes.
- New/updated targeted tests pass.
- Changed modules pass ruff, mypy or scoped type checks where repo-standard, and compile checks.
- Final handoff states branch, commit(s), commands, evidence, safety proof, limitations, and merge readiness.

## Stop conditions

Stop and report immediately if any stop condition in `STOP_CONDITIONS.md` is triggered.

## Final response required from local agent

Use `FINAL_HANDOFF_TEMPLATE.md`. Include:

- Branch / HEAD.
- Commit list.
- Summary of implemented changes.
- Commands run.
- Evidence file inventory.
- Test and validation results.
- DB-copy proof.
- Raw-safety/no-writeback proof.
- Known limitations.
- Residual-work audit result.
- Whether ready to merge.
