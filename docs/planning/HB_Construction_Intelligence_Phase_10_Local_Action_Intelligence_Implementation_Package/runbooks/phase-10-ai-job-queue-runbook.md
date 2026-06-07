# Phase 10 AI Job Queue Runbook

## Dry run

```bash
hb-assistant second-brain ai-jobs status --json
hb-assistant second-brain ai-jobs enqueue --job-type extract_email_tasks --dry-run --json
hb-assistant second-brain ai-jobs run --dry-run --max-items 10 --json
```

## Apply-local

Only after dry-run proof:

```bash
hb-assistant second-brain ai-jobs run --apply --confirm --max-items 10 --json
```

Apply-local may write local candidate rows only. It may not perform external writeback.
