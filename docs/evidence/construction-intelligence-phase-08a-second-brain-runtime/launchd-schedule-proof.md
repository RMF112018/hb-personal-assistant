# Phase 08A — Launchd Scheduling Dry-Run Install Proof (Prompt 13)

Operator runbook + a **dry-run install preview** for scheduling the second-brain daily brief
(`hb-assistant second-brain daily-brief generate`) at 20:00 local, generating the **following**
day's brief in `--mode apply`. The tool writes no plist, never invokes `launchctl`, and
enables no background behavior; logs live outside the repo; the preview persists metadata only
(`mode='dry_run'`). Automation hardening is handed off to the Phase 08B Automation Health Agent.

## Repo-truth preflight

| Check | Result |
| --- | --- |
| `git rev-parse HEAD` (pre-commit) | `4ad31d3` (Prompt 12) |
| Package-cited baseline | `c2656e1c` — does **not** match local repo; repo truth governs |
| `schema_version` | 26 (unchanged — no migration) |
| `contract_table_count` | 141 (unchanged) |
| Table used | `launchd_schedule_previews` (V26; first writer here; `mode CHECK(='dry_run')`, `external_writeback_performed CHECK(=0)`) |

## Files changed

Created:
- `construction/second_brain/daily_brief/scheduling.py` — dry-run preview + proof
- `tests/test_daily_brief_schedule.py`
- `docs/runbooks/phase-08a-second-brain-daily-brief-scheduling.md`
- `docs/architecture/69-phase-08a-launchd-scheduling-runbook-and-dry-run-install.md`
- evidence: `launchd-schedule-proof.json`, `launchd-schedule-preview.json`, this file

Modified:
- `cli/second_brain.py` — `daily-brief schedule-preview` + `generate` optional `--date` / `--day-offset`
- `daily_brief/store.py` — `write_launchd_schedule_preview` / `read_latest_launchd_schedule_previews`
- `daily_brief/models.py` — `LaunchdSchedulePreview`
- `daily_brief/__init__.py`, `second_brain/__init__.py`
- `resources/config/phase_08a_daily_brief_policy.seed.yaml` — additive `schedule` section

## Validation commands and results

| Command | Result |
| --- | --- |
| `python -m compileall -q src tests` | exit 0 |
| `ruff check .` | All checks passed |
| `mypy src` | Success: 240 source files (benign pre-existing unused-override note) |
| `pytest tests/test_daily_brief_schedule.py` (+ generate CLI, policy) | all passed |
| `pytest -m "not live and not integration and not manual"` | exit 0 (full suite green) |
| `construction-agent validate --json` | `{total:4, passed:4, ok:true}` |
| `data-quality table-inventory --json` | `schema_version=26`, `contract_table_count=141` (unchanged) |
| `data-quality no-writeback-proof --json` | `proof_passed=true` |
| `second-brain daily-brief schedule-preview --json` | exit 0 (dry-run preview; no install) |
| `second-brain daily-brief generate --day-offset 1 --json` | exit 0 (tomorrow's brief, dry-run) |

## Evidence proof

`launchd-schedule-proof.json` → `proof_passed: true` (proof
`phase_08a_launchd_schedule_dry_run`):
- Persisted preview row has `mode='dry_run'` (the table CHECK forbids any other value) and
  `external_writeback_performed=0`.
- `program_arguments_redacted` schedule the command
  `second-brain daily-brief generate --day-offset 1 --mode apply --emit-receipt`.
- `StartCalendarInterval = {Hour:20, Minute:0}`; logs resolve outside the repo
  (`logs_outside_repo=true`).
- `plist_path_redacted` / `log_dir_redacted` are populated and redacted (`$HOME`→`~`); no
  secrets/tokens and no raw home path leak.
- `no_plist_written=true` — this code path never writes a plist or calls `launchctl`.

`launchd-schedule-preview.json` — a sample rendered preview (label, schedule, redacted plist,
manual `launchctl` commands, Phase 08B handoff).

## Guardrail proof points

- **Dry-run install only**: no plist is written and `launchctl` is never invoked by the tool;
  `test_table_rejects_non_dry_run_mode` confirms the DB CHECK forbids a non-dry-run row.
- **Logs outside repo**: log paths derive from `PathPolicy().get_logs_dir()` under
  Application Support; `logs_outside_repo` asserted in proof + tests.
- **No hidden background behavior**: scheduling occurs only when the operator runs the
  documented `launchctl load` command themselves (runbook §3).
- **Redaction / no leakage**: `$HOME`→`~`; `test_preview_paths_are_redacted` asserts the real
  home string is absent from the serialized preview.
- **Metadata-only**: preview rows carry label + redacted paths + schedule JSON only; guard
  column 0.

## Reconciliations / known limitations

- No real launchd install / enable, no `launchctl` invocation — Phase 08B owns hardening.
- The legacy `automation/launchd_manager.py` (`run morning`) is intentionally not reused or
  modified.
- `weekend_behavior` is recorded but not enforced (a `StartCalendarInterval` with only
  Hour/Minute fires daily); enforcement is a Phase 08B concern.

## Next prompt readiness

- Schema final at V26 / 141 tables; Prompt 06–12 proofs unchanged.
- Phase 08B Automation Health Agent can consume the persisted `launchd_schedule_previews`
  rows + the runbook as its starting contract (real install, health checks, retries, weekend
  logic, alerting).
