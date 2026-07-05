# 04 — Mac Scheduler Status (report only)

Per operator decision, N8A **reports** the Mac single-writer scheduler status and does **not** unload, uninstall, or mutate it.

## Findings (read-only, this session)
- `launchctl list | grep com.hb.personal-assistant` → `-\t0\tcom.hb.personal-assistant.scheduler.production` — **loaded but not running** (`-` = no PID; last exit `0`).
- Plist `~/Library/LaunchAgents/com.hb.personal-assistant.scheduler.production.plist` present (`1192` bytes).
- `ProgramArguments`: `/Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant scheduler … --environment production`; `StartCalendarInterval` Hour `20` Minute `0` (daily 20:00). Logs under `~/Library/Application Support/HB Personal Assistant/logs/`.
- It targets the **Mac** venv + **Mac** app-support DB — a *different* DB from the NAS canonical `/volume2/personal-assistant/app-support/db/hb-personal-assistant.sqlite`.
- No `uvicorn` / `analytics.api` / `hb-assistant scheduler run` / `second-brain` / `source-watch` process running on the Mac; port `8000` not listening.

## Assessment
Because the watcher lease + run lock coordinate only when both hosts share the same DB/locks dir, this Mac agent is **not** lease-coordinated with the NAS DB; real overlap would require their source roots to point at the same synced folders. N8A enables **no** NAS-side continuous jobs, so this is **not an N8A blocker**.

## Action item (carried to N8B/N9)
Before the NAS owns a scheduler, unload the Mac agent so only the NAS writes the canonical DB:
```
launchctl unload -w ~/Library/LaunchAgents/com.hb.personal-assistant.scheduler.production.plist
#   or: hb-assistant scheduler uninstall --environment production
```
**Not performed in N8A (report-only).**
