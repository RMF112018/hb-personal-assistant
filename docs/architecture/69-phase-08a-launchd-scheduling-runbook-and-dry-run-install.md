# 69 — Phase 08A Launchd Scheduling Runbook & Dry-Run Install Preview

Status: implemented (Phase 08A Synthesized Prompt 13). Builds on records 57–68.

- Dry-run install **preview only**; no plist written, no `launchctl` invoked, no background
  behavior enabled. Metadata-only persistence; schema/contract-table count unchanged
  (V26 / 141). Logs outside the repo; all paths redacted. Automation hardening is owned by
  the Phase 08B Automation Health Agent.

## Purpose

Provides the operator runbook + a dry-run launchd install preview for scheduling
`hb-assistant second-brain daily-brief generate` (default: 20:00 local, generating the
**following** day's brief, `--mode apply`). The preview renders a launchd plist, computes
readiness, lists the manual `launchctl` commands the operator must run themselves, and
persists a metadata-only `mode='dry_run'` row. Nothing is installed or enabled.

## Repo-truth reconciliation (decisive)

- **No schema change.** The V26 `launchd_schedule_previews` table
  (`mode CHECK(mode='dry_run')`, `label`, `schedule_json`, `plist_path_redacted`,
  `log_dir_redacted`, `external_writeback_performed CHECK(=0)`) existed with no writer; this
  prompt adds the first (dry-run-only) writer. Schema stays V26 / 141 contract tables.
- **Legacy launchd untouched.** `automation/launchd_manager.py` is hardcoded for the
  `run morning` job; reusing/modifying it would be automation hardening (Phase 08B scope), so
  the second-brain preview is a self-contained, separate label
  (`com.hb.personal-assistant.second-brain-daily-brief`).
- **Enabling tweak.** `daily-brief generate` `--date` is now optional (defaults to today) with
  a new `--day-offset` (used when `--date` is omitted), so the recurring 20:00 job can target
  tomorrow (`--day-offset 1`). `run_daily_brief` is unchanged; the CLI resolves the effective
  date. Existing generate tests pass `--date` explicitly and are unaffected.
- **Logs outside repo.** `PathPolicy().get_logs_dir()` →
  `~/Library/Application Support/HB Personal Assistant/logs/`.

## Seed

`resources/config/phase_08a_daily_brief_policy.seed.yaml` gains an additive `schedule`
section (label, time `20:00`, day_offset `1`, command_mode `apply`, weekend_behavior `run`,
logs_outside_repo, dry_run_install_only, phase_08b_owns_hardening,
automation_health_agent_handoff). The Prompt-11 policy test is unaffected.

## Code

- `daily_brief/scheduling.py` — `build_daily_brief_schedule_preview(...)` (reads the seed
  `schedule` section, resolves the executable + repo working dir, builds the redacted plist +
  ProgramArguments + log paths, lists manual `launchctl` commands, adds the Phase 08B handoff,
  optionally persists) + `build_launchd_schedule_proof()`. No plist write, no `launchctl`.
- `daily_brief/store.py` — `write_launchd_schedule_preview` (INSERT `mode='dry_run'`; guard
  column 0) + `read_latest_launchd_schedule_previews`.
- `daily_brief/models.py` — `LaunchdSchedulePreview` (`dry_run_install_only` forced True,
  `external_writeback_performed` forced False; rejects forbidden raw tokens in args).

## CLI

`hb-assistant second-brain daily-brief schedule-preview [--emit-receipt] [--json]` — emits
the plist preview, readiness, manual install commands, redacted log/plist paths, the Phase
08B handoff, and guardrails (exit 0). `daily-brief generate` gains optional `--date` +
`--day-offset`.

## Guardrails

Dry-run install only; the tool never writes a plist or invokes `launchctl`; no hidden
background behavior (scheduling requires the operator to run the documented `launchctl`
command). Logs outside the repo; metadata-only preview rows (guard column 0,
`mode='dry_run'`). All paths redacted (`$HOME`→`~`); no tokens/secrets/raw content; no
external writeback.

## Evidence

`docs/evidence/construction-intelligence-phase-08a-second-brain-runtime/`:
`launchd-schedule-proof.md` (+ `launchd-schedule-preview.json` sample), proof
`phase_08a_launchd_schedule_dry_run` `proof_passed: true`. Operator runbook:
`docs/runbooks/phase-08a-second-brain-daily-brief-scheduling.md`.
