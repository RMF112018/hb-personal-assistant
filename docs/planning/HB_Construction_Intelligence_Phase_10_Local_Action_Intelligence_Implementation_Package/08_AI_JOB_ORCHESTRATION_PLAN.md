# 08 AI Job Orchestration Plan

## Job lifecycle

1. `queued`
2. `running`
3. `succeeded`
4. `degraded`
5. `blocked`
6. `failed`
7. `cancelled`

## Trigger modes

- after source refresh;
- scheduled;
- on-demand from CLI;
- on-demand from UI;
- fixture/test.

## Required job controls

- per-environment queue isolation;
- max concurrency;
- cancellation;
- retry/backoff;
- timeout;
- model unavailable fallback;
- receipt emission;
- dry-run mode;
- source watermarking;
- idempotency key.

## Initial job types

- `normalize_entities`
- `extract_email_tasks`
- `extract_commitments`
- `classify_inbox_items`
- `match_email_calendar_project`
- `detect_followups_due`
- `prepare_daily_brief_candidates`
- `calendar_prep_scan`
- `index_obsidian_vault`
- `suggest_obsidian_tags`
- `prepare_claude_context_packet`

## Non-blocking rule

Source refresh should enqueue AI work or run a bounded dry-run summary. It must not block frontend launch or scheduled source refresh completion on a long model job.
