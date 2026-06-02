# Phase 08A — Second-Brain Daily Brief: Scheduling Runbook

Bobby-facing reference for scheduling the second-brain daily brief on macOS via `launchd`.

**This phase ships a dry-run install *preview* only.** The tool **never** writes a plist,
**never** calls `launchctl`, and enables **no** background behavior. The only way to actually
schedule the job is for you to run the documented `launchctl` command yourself. Automation
**hardening** (health checks, retries, weekend logic, failure alerting, real install/enable)
is owned by the **Phase 08B Automation Health Agent** — see the handoff at the end.

- Logs live **outside the repo**, under `~/Library/Application Support/HB Personal Assistant/logs/`.
- All preview paths are redacted (`$HOME` → `~`). The preview persists metadata only
  (`mode='dry_run'`) to the local `launchd_schedule_previews` table; no secrets/tokens/raw content.

## What the schedule does

| Field | Value |
| --- | --- |
| Label | `com.hb.personal-assistant.second-brain-daily-brief` |
| Time | **20:00 local**, every day (`StartCalendarInterval {Hour:20, Minute:0}`) |
| Brief date | the **following** day (`--day-offset 1`) |
| Mode | `apply` (writes the approved brief to the vault; still evaluation-gated) |
| Command | `hb-assistant second-brain daily-brief generate --day-offset 1 --mode apply --emit-receipt` |
| Stdout log | `~/Library/Application Support/HB Personal Assistant/logs/run-logs/launchd-second-brain-daily-brief.out.log` |
| Stderr log | `~/Library/Application Support/HB Personal Assistant/logs/error-logs/launchd-second-brain-daily-brief.err.log` |
| Plist (preview path) | `~/Library/LaunchAgents/com.hb.personal-assistant.second-brain-daily-brief.plist` |

Defaults are configurable in `resources/config/phase_08a_daily_brief_policy.seed.yaml`
(`schedule:` section).

## 1. Preview the schedule (safe; default)

```bash
# Dry-run preview only — renders the plist, readiness, and manual install commands.
hb-assistant second-brain daily-brief schedule-preview --json

# Persist a metadata-only preview row (mode='dry_run') to the local V26 table.
hb-assistant second-brain daily-brief schedule-preview --emit-receipt --json
```

Review the rendered `plist`, the `program_arguments_redacted`, and the log paths. Nothing is
installed by this command.

## 2. Verify the brief command works (dry-run, no vault write)

```bash
hb-assistant second-brain daily-brief generate --day-offset 1 --json          # tomorrow, dry-run
```

When you are ready, an apply run writes to
`<vault>/Work/HB Personal Assistant/12_Daily_Brief/<date>_daily_brief.md` (evaluation-gated):

```bash
hb-assistant second-brain daily-brief generate --day-offset 1 --mode apply --emit-receipt --json
```

## 3. Install the schedule (manual — operator-run)

The tool will not do this for you. Write the plist from the preview, then load it:

1. Copy the `plist` object from `schedule-preview --json` into
   `~/Library/LaunchAgents/com.hb.personal-assistant.second-brain-daily-brief.plist`
   (expand `~` to your home; ensure the log directories exist).
2. Load + (optionally) test it:

```bash
launchctl load -w ~/Library/LaunchAgents/com.hb.personal-assistant.second-brain-daily-brief.plist
launchctl kickstart -k gui/$(id -u)/com.hb.personal-assistant.second-brain-daily-brief   # test run now
```

3. Confirm logs appear under `~/Library/Application Support/HB Personal Assistant/logs/`.

## 4. Uninstall

```bash
launchctl unload -w ~/Library/LaunchAgents/com.hb.personal-assistant.second-brain-daily-brief.plist
rm ~/Library/LaunchAgents/com.hb.personal-assistant.second-brain-daily-brief.plist
```

## Guardrails

- Dry-run install only this phase; no plist written, no `launchctl` invoked by the tool.
- Logs outside the repo; preview rows are metadata-only (`mode='dry_run'`, guard column 0).
- No hidden background behavior — scheduling happens only when you run `launchctl` yourself.
- The brief command remains read-only against external systems and never performs source-system
  writeback; apply writes only the local Obsidian brief and is evaluation-gated.

## Handoff to Phase 08B Automation Health Agent

The following are **out of scope** here and owned by the Phase 08B Automation Health Agent:

- Real, idempotent install/enable (writing the plist + `launchctl bootstrap`) with rollback.
- Health checks (last-run freshness, exit-code monitoring), retries, and catch-up logic.
- Weekend / holiday behavior enforcement (the preview records `weekend_behavior` but does not
  enforce it; `launchd` here would fire daily).
- Failure alerting and run-ledger integration.

Phase 08B should consume the persisted `launchd_schedule_previews` rows + this runbook as its
starting contract.
