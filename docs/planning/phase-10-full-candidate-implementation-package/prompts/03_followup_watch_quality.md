# Prompt 03 — Follow-up Watch Quality

## Objective

Improve Phase 10 follow-up watch quality and operator usefulness.

The follow-up watch workflow must better distinguish:

- open loop
- waiting on Bobby
- waiting on others
- stale follow-up
- resolved/closed
- not actionable
- insufficient evidence

It must produce a review-safe final follow-up watch report and evidence showing real end-to-end behavior on safe data.

## Required repo-truth audit before implementation

Inspect:

- existing follow-up watch commands
- accepted task/commitment extraction
- V45 email follow-up enrichment table and engine
- daily-brief pending follow-up section
- idempotency rules
- model-routing profile for raw enrichment
- any follow-up tests/evidence already present

Record findings in:

```text
docs/evidence/phase-10-full-candidate-implementation/03-followup-watch-quality/00-repo-truth-audit.md
```

## Implementation requirements

1. Improve classification semantics without unsafe inference.

   Use deterministic source signals where possible. Use local model enrichment only as review-safe advisory metadata.

2. Add or refine a follow-up watch report.

   The final report should group items by operator action:

   - needs Bobby action
   - waiting on someone else
   - stale/no response
   - monitor only
   - closed/resolved
   - needs review/insufficient evidence

3. Preserve source traceability.

   Every item must carry candidate/source references sufficient for Bobby to inspect it through existing local workflows.

4. Add quality gates.

   Examples:

   - no source reference → cannot persist as actionable
   - contradictory signals → needs review
   - low confidence → advisory only
   - model unavailable → deterministic fallback
   - stale threshold must be explicit and configurable or documented

5. Improve daily-brief consumption if required.

   Follow-up watch output should feed the daily-brief pending section from Prompt 01 without duplicate/conflicting sections.

## Required final output evidence

Generate in:

```text
docs/evidence/phase-10-full-candidate-implementation/03-followup-watch-quality/
```

Required files:

- `README.md`
- `00-repo-truth-audit.md`
- `01-followup-watch-final-output.md`
- `02-followup-watch-final-output.json`
- `03-stale-followup-proof.json`
- `04-closed-loop-proof.json`
- `05-waiting-state-proof.json`
- `06-model-unavailable-proof.md`
- `07-daily-brief-consumption-proof.md`
- `08-safety-scan-results.txt`
- `09-guard-column-proof.json`
- `10-production-db-unchanged-proof.txt`
- `validation-commands.txt`
- `validation-results.md`
- `final-output-manifest.md`
- `changed-files.txt`
- `branch-state.txt`

## Validation

At minimum:

```bash
python -m compileall src tests
pytest -q tests -k "followup or follow_up or email_followup or waiting or stale"
```

Run lint/type checks on changed files.

## Commit

Suggested commit:

```text
feat(second-brain): improve phase 10 follow-up watch quality
```

After committing, wait exactly 10 minutes before Prompt 04:

```bash
sleep 600
```
