# Scheduled Refresh Graph Email/Calendar Integration v1 Evidence

Date: 2026-06-11

## Production Config

Local production config was updated:

- `automation.scheduler.enable_live_reads: true`
- `automation.scheduler.enable_procore_live_reads: true`
- `automation.scheduler.enable_graph_live_reads: true`

`config/config.yml` is local/ignored in this repo, so the evidence is runtime-based rather than a normal
tracked diff.

## Scheduler Preview

Command:

`./.venv/bin/hb-assistant scheduler install daily-source-refresh --environment production --backend launchd --dry-run --json`

Observed:

- `writes_files: false`
- `StartCalendarInterval: {"Hour": 20, "Minute": 0}`
- `ProgramArguments`: `.venv/bin/hb-assistant scheduler run daily-source-refresh --environment production --if-due`

## Scheduler Status

Command:

`./.venv/bin/hb-assistant scheduler status daily-source-refresh --environment production --json`

Observed:

- installed launchd backend: `true`
- `schedule_time_local: "20:00"`
- `live_reads_enabled: true`
- `enable_procore_live_reads: true`
- `enable_graph_live_reads: true`
- state health: `ok`

## Validation

Focused tests run:

- `./.venv/bin/pytest tests/test_sources_refresh.py -q` -> `33 passed`
- `./.venv/bin/pytest tests/test_launcher_scheduler.py -q` -> `76 passed`
- `./.venv/bin/pytest tests/test_scheduler_degraded_surfacing.py tests/test_email_calendar_structured_projection_remediation.py tests/test_phase_10_first_slice_projection_activation.py tests/test_phase_10_email_followup_candidate_projection.py -q` -> `42 passed`

The direct manual `/tmp` DB-copy run was not completed in this session because shell access to the
production Application Support DB path was rejected by the command policy. The focused scheduler tests
cover injected temp DB/profile behavior, dry-run no-write behavior, raw/full-body fetch suppression, and
read-only Graph/no-writeback guards.
