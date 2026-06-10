# Phase 10 — Top 3 Local-Model Agent Convergence Package

Repository: `RMF112018/hb-personal-assistant`  
Local repo path: `/Users/bobbyfetting/hb-personal-assistant`  
Target branch: `experiment/phase-10-top3-local-model-agent-convergence`  
Package path once copied into repo: `docs/planning/phase-10-top3-local-model-agent-convergence-package/README.md`  
Evidence root: `docs/evidence/phase-10-top3-local-model-agent-convergence`

## Objective

Implement the top three local-model agent candidates in one complete, no-residual-work run:

1. **Daily Brief Intelligence / Synthesis Convergence**
   - Make the daily brief's final browser, Obsidian, status, and JSON surfaces use one coherent, source-linked model-enrichment path.
   - The operator-facing section label must be exactly: **Model Enriched Intelligence**.
   - The section must include model enrichment metadata and source links / source identifiers in a review-safe way.
   - The behavior is **default-on** for the daily-run path, with an explicit disable flag.

2. **Scheduler / Daily-Run Live Hardening**
   - Make the scheduled daily run reliably produce the same final surfaces.
   - Preserve last successful brief, write clear failure/partial status, never auto-open browser.
   - Make scheduler install/status/diagnostics operator-legible.
   - Validate actual launchd command grammar, executable, working directory, log paths, output paths, and model readiness.

3. **Email Follow-Up Raw Enrichment Productionization**
   - Move V45 raw email follow-up enrichment from technically working / sometimes no-op into a production-ready daily-run stage.
   - Add eligibility/readiness reporting so no-op conditions are explicit and actionable.
   - Safely run bounded local-only enrichment in apply runs when eligible, then consume pending rows in the **Model Enriched Intelligence** section.
   - Preserve all V45 safety guarantees: no raw body/prompt/response persistence, no cloud fallback, capped apply, idempotency, source-link requirement.

This package is intentionally comprehensive. Do not leave follow-up work behind unless a stop condition is triggered and documented.

## Scope Lock

This is an implementation package. The local agent must modify code, tests, docs, and evidence as needed, but must not violate safety constraints.

### In scope

- Daily-run model-enriched intelligence convergence.
- Browser HTML / Obsidian / status JSON / CLI JSON surface convergence.
- Scheduler install/status/live proof hardening.
- Email raw enrichment eligibility, readiness, apply-stage integration, and pending-row consumption.
- New or modified tests.
- DB-copy live validation.
- Evidence bundle.
- Architecture note and runbook.
- Final integration audit.
- Cleanup of any docs that now overstate old behavior.
- Backward-compatible CLI aliases where existing flags already exist.

### Non-goals

- No cloud LLM use.
- No external writeback.
- No Procore writeback.
- No Microsoft Graph writeback.
- No calendar mutation.
- No email send or draft creation.
- No MCP raw exposure.
- No production DB mutation during validation.
- No destructive migration.
- No raw private content in repo files, tests, evidence, logs, or status outputs.
- No browser auto-open until separately approved after stability.

## Mandatory behavior decisions

The following product decisions are already made and must not be re-asked:

1. **Default-on:** Model Enriched Intelligence must be default-on for `second-brain daily-run run` and for installed scheduled daily runs. Provide an explicit disable flag such as `--no-model-enriched-intelligence`.
2. **Label:** The rendered section label must be exactly **Model Enriched Intelligence**.
3. **Content posture:** The section must include model enrichment and source links/source identifiers, but never raw content, prompts, responses, full URLs, tokens, secrets, join/download/signed links, unsafe HTML, or email dumps.
4. **Scheduled run:** The scheduled run should generate browser HTML and Obsidian outputs automatically but must not auto-open the browser.
5. **Raw enrichment:** Email raw enrichment can run automatically only inside bounded, local-only, cap-enforced apply runs and only after eligibility/readiness gates pass.

## Required working branch

```bash
cd /Users/bobbyfetting/hb-personal-assistant
git fetch origin
git checkout main
git pull --ff-only
git checkout -b experiment/phase-10-top3-local-model-agent-convergence
```

If the branch already exists, inspect it. Do not reset or force-push without explicit operator approval.

## Hard safety constraints

- Do not modify `main` directly.
- Do not merge.
- Do not rebase.
- Do not use cloud LLMs.
- Do not send emails.
- Do not create email drafts.
- Do not mutate calendar data.
- Do not perform Procore writeback.
- Do not perform Microsoft Graph writeback.
- Do not perform MCP raw exposure.
- Do not perform external writeback of any kind.
- Do not mutate production DB during validation.
- Use DB copies for live proof.
- Default write behavior remains dry-run/plan-safe except the scheduled daily-run apply path, which must still be explicitly installed/applied by the operator and must enforce caps.
- Any apply path must be capped, bounded, idempotent, source-linked, review-safe, and fail-closed.
- Do not persist raw prompts, raw model responses, raw email/document/calendar/Procore bodies, unsafe HTML, full URLs, signed/download/join URLs, credential-shaped strings, or private payloads into repo artifacts.
- Raw private content may only be used for ephemeral local model context or local terminal preview when explicitly gated.

## Required implementation order

Execute the prompt files in `prompts/` in numeric order. Do not skip a prompt. Each prompt has its own evidence requirements.

| Prompt | Purpose |
|---|---|
| 00 | Repo-truth and branch preflight |
| 01 | Unified requirements and design lock |
| 02 | Daily brief intelligence/synthesis convergence |
| 03 | Render surface convergence: browser, Obsidian, status |
| 04 | Daily-run default-on integration |
| 05 | Scheduler hardening and live status |
| 06 | Email raw enrichment eligibility/readiness |
| 07 | Email raw enrichment production pipeline |
| 08 | Pipeline-level convergence across all three candidates |
| 09 | CLI operator surface consolidation |
| 10 | Test suite implementation |
| 11 | DB-copy live proof and evidence generation |
| 12 | Docs, runbooks, architecture |
| 13 | Final integration audit |
| 14 | Residual-work elimination and final handoff |

## Required final operator surfaces

At completion, the operator must have:

1. `second-brain daily-run run` default-on **Model Enriched Intelligence**.
2. `second-brain daily-run run --no-model-enriched-intelligence` explicit fallback.
3. Browser brief containing **Model Enriched Intelligence** when safe.
4. Obsidian brief containing **Model Enriched Intelligence** when safe.
5. Status JSON containing safe model-enrichment counts, route metadata, source-link counts, and degradation reasons.
6. Scheduler install/status surfaces showing whether Model Enriched Intelligence and V45 raw enrichment are active.
7. Email raw enrichment readiness report showing eligible/ineligible counts and skipped reasons.
8. Daily-run receipt showing email raw enrichment stage execution or clean skip.
9. Runbook with exact manual test commands.
10. Evidence bundle proving no production DB mutation, no writeback, no raw leakage, and no residual work.

## Required final evidence files

Create these under `docs/evidence/phase-10-top3-local-model-agent-convergence/`:

```text
00-repo-state.md
01-branch-state.txt
02-schema-before-after.json
03-current-surface-audit.md
04-unified-design-contract.md
05-daily-brief-intelligence-convergence-proof.json
06-browser-model-enriched-intelligence-proof.html
07-obsidian-model-enriched-intelligence-proof.md
08-status-json-proof.json
09-scheduler-install-preview-proof.json
10-scheduler-status-proof.json
11-email-raw-enrichment-eligibility-proof.json
12-email-raw-enrichment-dry-run-proof.json
13-email-raw-enrichment-capped-apply-proof.json
14-email-raw-enrichment-idempotency-proof.json
15-daily-run-integrated-proof.json
16-model-unavailable-fallback-proof.json
17-forbidden-string-scan.txt
18-no-writeback-proof.md
19-guard-column-proof.json
20-production-db-unchanged-proof.txt
21-validation-results.md
22-cli-help-snapshots.md
23-output-path-safety-proof.md
24-known-limitations.md
25-final-handoff.md
26-residual-work-audit.md
```

Evidence must be raw-free. Use counts, hashes, source IDs, redacted paths, and safe metadata only.

## Acceptance criteria

All must be true:

- `second-brain daily-run run` defaults to Model Enriched Intelligence.
- The section label is exactly **Model Enriched Intelligence**.
- Final browser, Obsidian, status JSON, and CLI JSON agree on enrichment status and counts.
- Source-linked model bullets cite existing candidate/source identifiers only.
- Unsourced model output is dropped or withheld.
- Model unavailable produces deterministic fallback and explicit degraded/withheld status.
- V45 raw email follow-up enrichment has a readiness/eligibility report.
- V45 raw enrichment runs as a bounded, cap-enforced stage in daily-run apply mode when eligible.
- V45 raw enrichment cleanly skips when no eligible records exist and explains why.
- Scheduler install/status surfaces include the final model-enriched and raw-enrichment posture.
- Browser is not auto-opened.
- Last successful brief is preserved on failure/partial/degraded runs.
- Production DB hash is unchanged during validation.
- No external writeback occurs.
- Guard columns remain zero.
- New targeted tests pass.
- Changed modules pass ruff/mypy/compile.
- Evidence scan passes.
- Final handoff explicitly states no residual work remains, or names any blocked residual work with a stop-condition reason.

## Stop conditions

Stop and report immediately if any of these occur:

- Raw/private content appears in repo evidence, tests, logs, committed docs, browser proof, Obsidian proof, or status proof.
- Raw model prompts/responses are persisted or committed.
- Any cloud LLM route or fallback is introduced.
- Any external writeback path is invoked.
- Any email send/draft path is invoked.
- Any calendar mutation path is invoked.
- Any Procore writeback path is invoked.
- Any Graph writeback path is invoked.
- Any MCP raw exposure path is invoked.
- Production DB hash changes during validation.
- Model-enriched content is rendered as accepted fact instead of advisory/source-linked intelligence.
- A migration becomes necessary but cannot be proven additive, reversible, and safe.
- Apply path lacks a cap.
- Raw enrichment can run without source links.
- Browser output path or evidence output path points inside an unsafe/raw location.
- Final tests fail because of this package.
- The local agent cannot prove no residual work remains.

## Final response required from local agent

Use `templates/FINAL_HANDOFF_TEMPLATE.md`. Include:

- Branch / HEAD.
- Commit list.
- What changed for all three candidates.
- Commands run.
- Evidence files.
- Test results.
- Safety proof.
- DB proof.
- Known limitations.
- Residual-work audit result.
- Whether ready to merge.
