# Prompt 04 — Scheduler / Daily-Run Reliability

## Objective

Harden the scheduler and daily-run reliability path so Bobby's daily brief can appear at the intended stable file/URL path at 5:00 AM or the next time the machine is active.

Do not auto-open browser output. Preserve last successful brief. Write clear failure/partial status. Generate degraded brief only when safe.

## Required repo-truth audit before implementation

Inspect:

- daily-run scheduler install command
- launchd plist generation
- daily-run status file behavior
- last-success pointer behavior
- failure/degraded paths
- retry/backoff behavior
- weekday/window policy
- output path policy and repo-containment guard
- existing tests/evidence for scheduler and daily-run

Record findings in:

```text
docs/evidence/phase-10-full-candidate-implementation/04-scheduler-daily-run-reliability/00-repo-truth-audit.md
```

## Implementation requirements

1. Make scheduled run behavior operator-legible.

   The final status file must clearly show:

   - last run started/completed
   - success/degraded/failure
   - final browser output path
   - final Obsidian output path
   - last successful output path
   - partial stage receipts
   - safe error summaries
   - no raw/private content

2. Ensure scheduler install preview is safe and clear.

   Scheduler install should have a dry-run/preview mode and require explicit apply/confirmation for writes.

3. Preserve previous successful brief.

   A failed or degraded run must not overwrite the pointer to the last successful brief.

4. Harden next-active-machine semantics as far as repo truth allows.

   If launchd can run at wake/next available, document and implement the appropriate plist keys. If exact behavior is limited by macOS, state that honestly in docs/evidence.

5. Ensure browser output is stable but not auto-opened.

   Generate at a stable local path and record it in status. Do not auto-open unless an explicit future flag exists and is off by default.

6. Add failure simulation and partial success proof.

## Required final output evidence

Generate in:

```text
docs/evidence/phase-10-full-candidate-implementation/04-scheduler-daily-run-reliability/
```

Required files:

- `README.md`
- `00-repo-truth-audit.md`
- `01-scheduler-install-preview-final-output.txt`
- `02-scheduler-status-final-output.json`
- `03-success-status-proof.json`
- `04-degraded-status-proof.json`
- `05-failure-status-proof.json`
- `06-last-success-preservation-proof.md`
- `07-stable-output-path-proof.md`
- `08-launchd-plist-preview.plist`
- `09-safety-scan-results.txt`
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
pytest -q tests -k "scheduler or daily_run or launchd or status or last_success"
```

Run lint/type checks on changed files.

## Commit

Suggested commit:

```text
fix(second-brain): harden phase 10 daily-run scheduler reliability
```

After committing, wait exactly 10 minutes before Prompt 05:

```bash
sleep 600
```
