# Prompt 01 — Daily Brief Surface Convergence

## Objective

Implement Phase 10 Daily Brief Surface Convergence.

Make the final operator-facing daily brief surfaces consistently reflect the safe Phase 10 intelligence already implemented in the repo, especially V45 pending email follow-up enrichment.

The final daily-brief outputs must converge across:

- polished browser HTML
- Obsidian markdown
- JSON/payload output if present
- redacted status file
- local deterministic fallback/degraded output

This prompt must not introduce external writeback or raw-content exposure.

## Required repo-truth audit before implementation

Inspect the current code paths for:

- `daily-run run`
- `pipeline run`
- `daily_brief_context_packet`
- `daily_brief_llm_synthesis`
- `daily_brief_render`
- `daily_run_html`
- `email_followup_pending`
- V45 `email_followup_enrichments`
- the existing `--with-email-raw-enrichment` and `--with-intelligence` flags
- existing browser, Obsidian, JSON, and status outputs

Record findings in:

```text
docs/evidence/phase-10-full-candidate-implementation/01-daily-brief-surface-convergence/00-repo-truth-audit.md
```

## Implementation requirements

1. Define a single review-safe pending follow-up section contract.

   It must include only review-safe fields, such as:

   - thread/candidate/source identifier
   - subject/title if already sanitized by existing code
   - waiting/open-loop status
   - recommended next action
   - confidence/quality labels
   - due/staleness metadata
   - source references
   - model route metadata if already review-safe
   - redaction/safety flags

   It must not include raw body, raw prompt, raw model response, email address dumps, URLs, tokens, HTML bodies, signed/download links, or join links.

2. Wire pending V45 email follow-up enrichments into the final render path.

   The section must appear in the final browser and Obsidian outputs when pending review-safe enrichment rows exist.

   The output must be deterministic and source-linked. Do not require model synthesis for the section to appear.

3. Preserve degraded/fallback behavior.

   If model synthesis is unavailable, the pending follow-up section must still be available in deterministic degraded output if its inputs are safe and present.

4. Keep `--with-email-raw-enrichment` semantics honest.

   If this flag only enriches payloads, update the code/docs so it also wires to final surfaces or rename/reword behavior to match reality.

5. Keep status files redacted.

   Status may include counts, timestamps, safe section names, and paths only. It must not contain row-level sensitive content.

6. Include a safety scan helper if no suitable helper exists.

   The helper must scan generated daily-brief outputs for forbidden strings/patterns before writing evidence.

## Required final output evidence

Generate the following in:

```text
docs/evidence/phase-10-full-candidate-implementation/01-daily-brief-surface-convergence/
```

Required files:

- `README.md`
- `00-repo-truth-audit.md`
- `01-no-row-render-proof.json`
- `02-seeded-v45-render-proof.json`
- `03-browser-final-output.html` or a committed sanitized/synthetic equivalent
- `04-obsidian-final-output.md` or a committed sanitized/synthetic equivalent
- `05-status-final-output.json`
- `06-degraded-output-proof.md`
- `07-safety-scan-results.txt`
- `08-guard-column-proof.json`
- `09-production-db-unchanged-proof.txt`
- `validation-commands.txt`
- `validation-results.md`
- `final-output-manifest.md`
- `changed-files.txt`
- `branch-state.txt`

The browser and Obsidian proof artifacts must represent what Bobby is intended to see after this candidate in real usage. Use synthetic or sanitized temp DB data if live data is absent.

## Validation

Run targeted tests for all changed daily-brief, email-followup, renderer, and CLI code.

At minimum:

```bash
python -m compileall src tests
pytest -q tests -k "daily_brief or daily_run or followup or email_followup or render"
```

Run lint/type checks for changed files if available:

```bash
ruff check <changed-files>
mypy <changed-python-files>
```

If exact commands differ by repo convention, use repo-truth equivalents and record them.

## Commit

Commit only this candidate's work and evidence.

Suggested commit:

```text
feat(second-brain): converge phase 10 daily brief surfaces
```

After committing, wait exactly 10 minutes before Prompt 02:

```bash
sleep 600
```
