# Command Transcript Summary (redacted)

Local-only, `/tmp` Dev DB copy. Raw outputs stored outside the repo; only safe fields shown.

| # | Command (abbrev.) | Exit | Key result |
| --- | --- | --- | --- |
| 1 | `local-model route --task-family daily_brief_synthesis_quality` | 0 | `selected_profile=brief_synthesis`, `reason_code=selected_routed`, `no_cloud=true` |
| 2 | `daily-brief intelligence --date 2026-06-09 --db <copy> --dry-run` (pre) | 0 | `enriched=true`, coverage 1.0, 12 bullets, no fallback, ~53s |
| 3 | `daily-run run --db <copy> --dry-run --with-intelligence --no-synthesize --no-open-browser --no-generate-browser` | 0 | status `success`, dry_run, `total_persisted=0`, browser output suppressed |
| 4 | `daily-run run --db <copy> --apply --max-persist-per-stage 10 --max-total-persist 30 --with-intelligence --no-synthesize --no-open-browser --no-generate-browser` | 0 | status `success`, 5 stages ok, egress clean, intelligence enriched (`pipeline_apply`) |
| 5 | `daily-brief intelligence --date 2026-06-09 --db <copy> --dry-run` (post) | 0 | `enriched=true`, coverage 1.0, candidate_count 20 |
| 6 | `daily-run run --db <copy> --apply ... --no-intelligence` (idempotency) | 0 | `total_persisted=0`, candidate count unchanged |
| 7 | `local-model eval --suite daily-brief --synthetic` | 0 | `eval_mode=synthetic_offline_contract`, json/schema/redaction rates 1.0 |

Guard-column sum 0; redaction/forbidden scans clean; production DB unchanged. See per-topic proofs.
