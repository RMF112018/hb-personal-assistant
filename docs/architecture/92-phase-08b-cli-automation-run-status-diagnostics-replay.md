# Phase 08B Addendum Prompt 06 — CLI Automation Run, Status, Diagnostics, and Replay (Architecture Note)

**Status**: Implemented. Additive CLI surface over P03–P05 executor. No schema change. Gate remains deferred_not_blocking.

## Summary of Changes
- New commands under `hb-assistant second-brain automation`:
  - `run --kind --date --catch-up --dry-run/--no-dry-run --apply --confirm --json` : wraps executor, produces required JSON (command, mode, status, run_id, target_date, stage_summary, retry_summary, lock_status, replay_eligibility, recovery_command_redacted, guardrails).
  - `replay --run-id --stage --apply --confirm --json` : exposes P05 replay path with same JSON shape.
  - `status --json` : aggregates latest registry run + lock + eligibility + summaries + redacted recovery (new grammar).
  - `diagnostics --run-id --json` : per-run detailed stages/steps + retry receipts + eligibility + redacted rec.
  - `last-good-run --kind --json` : last succeeded for kind.
- Builders in automation_executor.py: `build_automation_status`, `build_automation_diagnostics` (produce the exact required shape; used by CLI and to generate evidence previews).
- Updated recovery_recommendation to suggest P06 `run` / `replay` cmds.
- Evidence: automation-status-preview.json + automation-diagnostics-preview.json (generated, contain all required keys, no raw, guardrails, 34).
- Exports, basic test coverage.
- Arch 92- + 00-README additive.

## Design Notes
- "run" supports suggested grammar (kind/date/catch-up); maps to ExecutionRequest + run_automation_execution.
- Replay reuses P05 fields/validate/selection/link/dedup/block logic.
- Status/diagnostics are read-only (registry + lock + health/retry surfaces + P05 eligibility).
- All payloads include the exact required fields + guardrails (read-only for status/diag, confirm for mutating, redacted recovery).
- No unrelated changes; only P06 files touched.

## Verification
Full matrix + explicit run of all suggested commands (dry + status/diag/last-good) + evidence gen + key asserts passed. Gate still deferred.

See manifest and evidence. Repository truth authoritative. Guardrails preserved. No overstatement.