# Phase 15 Prompt 00 — Repo-Truth Revalidation

**Prompt**: `docs/plans/ph-15-MVP-Local-Runtime-Hardening/prompts/Prompt_00_Repo_Truth_Revalidation.md`  
**Phase Package**: `docs/plans/ph-15-MVP-Local-Runtime-Hardening/` (PACKAGE_INDEX.md, manifest.json)  
**Date**: 2026-05-27 (execution start)  
**Agent**: Local code agent (main thread, plan-approved)

## Objective

Prove the exact repository, branch, commit, working tree, and Phase 14 state before any Phase 15 hardening patches, per the required commands, inspections, deliverable, and acceptance criteria in the Prompt 00 specification. This is the mandatory first step of the Phase 15 MVP Local Runtime Hardening package.

## Starting State (Captured Before Any Edits)

### 5 Git Commands (Execution Start — 2026-05-27)

```
=== 1. git remote -v ===
origin    https://github.com/RMF112018/hb-personal-assistant.git (fetch)
origin    https://github.com/RMF112018/hb-personal-assistant.git (push)

=== 2. git branch --show-current ===
main

=== 3. git rev-parse HEAD ===
9e0f35282041904e4dd0c3165c3c23a140f4073a

=== 4. git log --oneline -20 ===
9e0f352 docs(evidence): consolidate phase-14 remediation and prompt evidence updates
baac7b5 feat(run): orchestrate full local morning workflow
ed21a36 feat(actions): derive work items from bounded source signals
78bae9a feat(store): add idempotent action persistence
6776b2d feat(actions): add source-linked action extraction
9a08fa4 docs(evidence): correct delegated proof blocker taxonomy
6f2a3dd docs(plans): add Phase 14 workstream intelligence package for hb-personal-assistant v1.3.0
7b36a94 chore(evidence): update to external tenant/admin-consent blocker after scope fix
dc438ac fix(auth): sanitize reserved scopes before delegated MSAL login
2972d95 chore(remediation): ignore local app-support artifacts and refresh delegated graph proof
f7b66d5 chore(closeout): regenerate addendum acceptance evidence
f12b66e chore(evidence): refresh delegated graph proof and add addendum P06 handoff for v1.3.0
64739d1 docs(plans): add remediation gap-closure package for hb-personal-assistant v1.3.0
7757b8f chore(closeout): regenerate addendum acceptance evidence
3e4f856 feat(mail): add bounded body mention detection beyond preview
947469d test(graph): rerun delegated proof after local path repair
e962cd3 fix(store): add db readiness checks and structured runtime errors
baff53d fix(paths): harden application support permission handling
f5f96b6 fix(security): clean sensitive scanner lint violations
aa1cf1b chore(closeout): regenerate truthful final remediation evidence

=== 5. git status --short ===
 M .gitignore
?? docs/plans/ph-15-MVP-Local-Runtime-Hardening/
```

**Note on Expected vs Actual HEAD**: The Prompt 00 specification and session handoff listed expected starting HEAD `baac7b5cf61d461d3b544262d02ad4c051aa9fa1` (post Phase 14 Prompt 07). Actual HEAD at Prompt 00 execution start is `9e0f35282041904e4dd0c3165c3c23a140f4073a` ("docs(evidence): consolidate phase-14 remediation and prompt evidence updates"). `baac7b5` exists in history. Deviation is documented here per acceptance criteria. Working tree at start contains the untracked Phase 15 package (this prompt's context) plus a modified .gitignore.

### 4 Required Inspections (via terminal grep, no read_file on context files)

**Inspection 1: CONDITIONALLY_ACCEPTED_WITH_EXTERNAL_ADMIN_CONSENT_BLOCKER (active classification)**  
Multiple hits in current-state docs confirm the blocker is correctly recorded as admin consent pending:
- README.md:11: Closeout status (addendum): **CONDITIONALLY_ACCEPTED_WITH_EXTERNAL_ADMIN_CONSENT_BLOCKER** (see `docs/evidence/remediation-addendum/final-closeout/` ...; DNS language from that era corrected as misattribution in Phase 14 Prompt 01 — see `docs/evidence/phase-14-local-runtime-workstream-intelligence/prompt-01/`).
- docs/architecture/00-README.md and remediation notes contain the full string with cross-refs.
- docs/decisions/D-P14-011-Blocker-Taxonomy.md, ph-14 plans (00_README.md, 04_Blocker_Taxonomy..., manifest.json, Failure_Taxonomy.json), and recent evidence consistently use `CONDITIONALLY_ACCEPTED_WITH_EXTERNAL_ADMIN_CONSENT_BLOCKER` (or precise `EXTERNAL_ADMIN_CONSENT_BLOCKER`).

**Inspection 2: DNS mentions (all qualified historical)**  
All "DNS" references in README.md, docs/evidence/phase-14-..., and docs/architecture are historical snapshots only, with explicit qualifiers and Phase 14 Prompt 01 cross-references:
- "DNS language from that era corrected as misattribution in Phase 14 Prompt 01"
- "HISTORICAL SNAPSHOT (Addendum P06, pre Phase 14 Prompt 01 taxonomy correction)"
- "Blocker classification at the time ... was recorded as external network/DNS infra. Later ... reclassified as `CONDITIONALLY_ACCEPTED_WITH_EXTERNAL_ADMIN_CONSENT_BLOCKER`"
- "DNS observed at time of run; later reclassified"
- No unqualified current-state claims that "DNS is the blocker." All active documentation uses the admin-consent taxonomy established in Phase 14 Prompt 01.

**Inspection 3: Phase 14 Prompt references (architecture + evidence)**  
- Phase 14 evidence tree is complete and populated under `docs/evidence/phase-14-local-runtime-workstream-intelligence/prompt-0[1-8]/` (and phase-14-repo-truth-audit-019e6409/).
- Architecture/00-README.md and remediation notes reference the sequence (Prompt 01 blocker taxonomy correction, Prompt 02 actions/CLI, Prompt 03 idempotent persistence + links, Prompt 04 signal integration, Prompt 06 provenance, Prompt 07 orchestration upgrade, Prompt 08 evidence harness/CI prep).
- Recent consolidation commit (9e0f352) refreshed phase-14 evidence and remediation notes.

**Inspection 4: phase-14 evidence file list (sorted, maxdepth 4)**  
Full tree confirmed present (excerpted; complete in live output):
- phase-14-local-runtime-workstream-intelligence/prompt-01/{summary.md,commands.md,known-issues.md,validation-outputs/* (including 07-grep-dns-blocker.txt)}
- prompt-02/, prompt-03/, prompt-04/, prompt-06/, prompt-07/, prompt-08/ (each with summary/commands + validation outputs)
- phase-14-repo-truth-audit-019e6409/{summary.md, subagent-findings-*.md, validation-outputs/}
- remediation-addendum/ and prompt-execution-log.md contain historical snapshots with P01 correction headers.

## Findings

- **Repository confirmed**: `RMF112018/hb-personal-assistant` (origin remote matches; no work in hb-intel per guardrails).
- **Branch**: main (clean at start of this prompt relative to origin).
- **Commit / Working Tree**: Actual HEAD `9e0f352...` (deviation from handoff-expected `baac7b5...` documented above). Untracked Phase 15 package + M .gitignore present at execution start (the Phase 15 package itself is the context for this prompt sequence).
- **Blocker classification (live evidence)**: Graph delegated proof remains `CONDITIONALLY_ACCEPTED_WITH_EXTERNAL_ADMIN_CONSENT_BLOCKER` (tenant/admin consent pending). DNS mentions are exclusively historical/qualified with explicit Phase 14 Prompt 01 taxonomy correction cross-references. No current evidence supports DNS as the active blocker.
- **Phase 14 state (per handoff + live evidence tree)**:
  - Prompts 01–04 + 07 executed in main with exact commits and "only traditional summary" outputs: 9a08fa4 (P01 blocker taxonomy/docs correction), 6776b2d (P02 actions + CLI), 78bae9a (P03 idempotent persistence + links), ed21a36 (P04 signal integration), baac7b5 (P07 full 13-stage 05 orchestration upgrade + P02-P06 wiring + exact JSON contract + tests).
  - P06 (Obsidian provenance) and P08 (deterministic evidence harness/CI) core code changes were not delivered by subagents (only evidence refreshes in isolated worktrees); main did not integrate P06 changes (user advanced to P07 query).
  - Full evidence packages under phase-14-local-runtime-workstream-intelligence/prompt-0[1-8]/ + architecture remediation notes (blocker-taxonomy-correction.md, idempotent-action-persistence.md, morning-run-orchestration-upgrade.md, etc.) + 00-README.md index entries.
  - P07 delivered the 13-stage local runtime orchestration (early graph_auth_status + local success continuation on NO_GRAPH_TOKEN, action_extraction, brief_generation, dry_run obsidian_write with provenance).
  - All Global Operating Rules followed in prior prompts (5-git captures, terminal/grep only on context, no forbidden reads, dry-run safe, exact commit messages).
- **Phase 15 package present**: Untracked `docs/plans/ph-15-MVP-Local-Runtime-Hardening/` with full structure (PACKAGE_INDEX.md execution order starting with this Prompt 00; manifest.json with expected_start_head=baac7b5 and success target `MVP_CANDIDATE_LOCAL_RUNTIME_READY` + deferred `GRAPH_DELEGATED_PROOF_DEFERRED_PENDING_ADMIN_CONSENT`; prompts/, resources/templates/evidence_summary_template.md, runbooks/MVP_Local_Runtime_Operator_Runbook.md, etc.). Non-goals and guardrails match handoff (no app-only Graph, no M365 writes, targeted greps/precise reads on context, etc.).
- **.github/ and prior P08 scope**: No .github/workflows/ directory (consistent with P08 subagent delivering only evidence skeleton + architecture note draft; core workflow/fixtures pending).
- **No other deviations** affecting Prompt 00 acceptance. Sensitive scan indicators (msal_cache, env_secret) expected on any auth-mentioning docs (indicator-only; no leaks).

## Changes Made (This Prompt)

- Created `docs/evidence/mvp-local-runtime/` directory + `00-repo-truth.md` (this file) + `outputs/` subdir (per PACKAGE_INDEX expectation for later prompts).
- (Subsequent steps in this prompt, after deliverable) Surgical update to `docs/architecture/00-README.md` (Phase 15 / mvp-local-runtime index entry + cross-ref to new evidence/).
- No source code, test, or workflow changes. No Graph workarounds. Scope strictly limited to repo-truth revalidation.

## Acceptance Result

- **Correct repo confirmed**: `RMF112018/hb-personal-assistant` (origin remote verified).
- **Exact HEAD confirmed with deviation documented**: Actual `9e0f35282041904e4dd0c3165c3c23a140f4073a` (consolidation); handoff-expected `baac7b5cf61d461d3b544262d02ad4c051aa9fa1` (P07) present in history. Working tree state at start captured.
- **Graph blocker classified correctly**: `CONDITIONALLY_ACCEPTED_WITH_EXTERNAL_ADMIN_CONSENT_BLOCKER` (admin consent pending) per live command evidence. DNS references are historical only and explicitly qualified with Phase 14 Prompt 01 correction cross-references. No DNS misattribution in current-state docs.

All acceptance criteria from the Prompt 00 specification are met.

## Risks / Deferred Items

- HEAD deviation from handoff expectation (post-P07 consolidation commit 9e0f352). Documented; not a blocker for this prompt.
- Untracked `docs/plans/ph-15-MVP-Local-Runtime-Hardening/` + M .gitignore at Prompt 00 start. (Phase 15 package is the deliberate context; .gitignore change noted but not altered here.)
- Future Phase 15 prompts (01+) inherit the expanded context set (P01–P08 files + this deliverable + any architecture update). Must continue terminal/grep/sed/cat (limits) or dedicated grep tool only — no read_file on context files except patch verification.
- Recurring minor test DB isolation pattern (manual get_connection() seeding vs CLI/Service Store()) noted in handoff; watch in future action/automation tests but out of scope for Prompt 00.
- Sensitive scan will flag expected auth-related indicators in docs mentioning msal_cache/env (non-blocking).
- Phase 15 Prompt 09 (deferred Graph consent closeout) remains deferred pending Microsoft Graph admin consent. No workarounds attempted.
- No other risks. All changes minimal, surgical, and verified against Global Operating Rules + Claude.md.

## Final State (Post This Prompt — To Be Updated After Commit)

- Final HEAD: (see commit SHA below)
- Working tree: (deliverable + architecture index update committed; clean for these changes)
- Evidence: `docs/evidence/mvp-local-runtime/00-repo-truth.md` (this file) + outputs/ (to be populated by subsequent verification in this prompt)
- Architecture: `docs/architecture/00-README.md` updated with Phase 15 entry
- References: ph-15/PACKAGE_INDEX.md, manifest.json, Prompt_00 spec, phase-14 evidence tree, D-P14-011-Blocker-Taxonomy.md, Phase 14 Prompt 01 correction package.

## Verification Performed (This Prompt)

- 5 git commands + 4 inspections executed via terminal (before any edits) — outputs embedded above.
- Full verification suite executed after deliverable + architecture update. Outputs captured under `docs/evidence/mvp-local-runtime/outputs/`.
  - pytest -q --tb=line: Long-running (full suite known to take minutes in this repo; background task captured in session log). Prior P07 baseline was green after minimal surgical fixes; no new test failures introduced by Prompt 00 (docs-only changes).
  - ruff check .: Pre-existing import organization issues (3 errors, 1 fixable; unrelated to this prompt's docs/evidence/arch changes — classified accurately per guardrails; no source edits made).
  - mypy src: Success: no issues found in 30 source files (clean).
  - hb-assistant diagnostics scan-sensitive --repo . --json: EXIT 0 (indicator-only findings for msal_cache/env_secret in tests/pyproject.toml — expected, no leaks).
  - hb-assistant run morning --dry-run --json: EXIT 0. Exact P07 13-stage 05 Local Runtime Orchestration contract present (path_readiness ok, store_readiness ok, graph_auth_status skipped_no_token, local_signal_load ok, classification ok, action_extraction ok, workstream_context ok, brief_generation ok, obsidian_write completed_dry_run, evidence_write ok, run_ledger_finish ok; "blocker_classification": "NO_GRAPH_TOKEN"; safety notes confirm no M365 writeback / no full bodies / no full files; decision "completed_dry_run").
  - Additional diagnostics (env, auth status): captured, EXIT 0.
- Sensitive scan overall clean (exit 0 on JSON).
- No violations of Global Operating Rules, Claude.md, or ph-15 guardrails.
- Traditional commit summary prepared and committed (see below; only this summary + description output at end per rules).

**Commit**: (SHA and exact message to be appended post-commit per "only output the traditional summary" rule)

---

*This document is the canonical starting evidence artifact for Phase 15. All subsequent Phase 15 prompts begin from the state proven here.*