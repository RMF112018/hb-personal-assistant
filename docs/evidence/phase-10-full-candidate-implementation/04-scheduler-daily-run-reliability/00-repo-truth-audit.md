# Repo-Truth Audit — Scheduler / Daily-Run Reliability (Prompt 04)

## Existing surfaces (mature)

| Concern | Location | State |
|---|---|---|
| Daily-run orchestrator | `…/local_ai/daily_run.py` `run_daily_local_agent` | Renders browser HTML + Obsidian + redacted status; preserves last-good on failure; refuses repo-contained output dirs; `--no-open-browser`. |
| Status writer | `_write_status` | latest + dated + last-successful pointer; pointer updated ONLY on fresh success; redacted (`~/…`) paths. |
| Scheduler installer | `…/local_ai/daily_run_scheduler.py` `DailyRunLaunchdManager` | Dry-run `preview_install`; `install` (apply via launchctl); `uninstall`; `status`; weekday-only via Mon–Fri `StartCalendarInterval` array; native catch-up-on-wake. |
| Scheduler CLI | `daily-run scheduler install/status/uninstall` | Dry-run/plan default; explicit `--apply`. |

## Gaps (Prompt requirement 1)

The status file carried all the pieces (status, stages, outputs, warnings) but **scattered** — there
was no single operator-legible summary, and no explicit wall-clock **started/completed** timestamps
(only the logical `run_timestamp`). Degraded was a separate bool, not a first-class result label.

## Decision (surgical)

Add an operator-legible consolidated `run_summary` block to the status file + run payload:
- `result` (success / **degraded** / partial / failure / skipped_weekend) — degraded is explicit;
- wall-clock `started_utc` / `completed_utc`;
- final output paths (browser / Obsidian / last-successful);
- `stage_receipts` (name + status only);
- `error_summary` (safe); `pending_followup_count`; `browser_auto_opened: false`.

No change to the scheduler installer (already complete: dry-run preview, plist, catch-up-on-wake), no
schema change, no auto-open, no writeback. macOS next-active-machine semantics are launchd-native
(a missed weekday `StartCalendarInterval` fires on the next wake; the date policy resolves it).
