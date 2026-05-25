# CLI Agent and Automation Specification

Prepared: 2026-05-25

## CLI

Command namespace: `hb-assistant`.

| Command | Purpose |
| --- | --- |
| auth login/status/logout/clear-cache | Delegated auth and cache lifecycle. |
| diagnostics env/auth/graph/scan-sensitive | Safe health checks and proof. |
| vault inspect | Read-only Obsidian convention inspection. |
| sync mail/calendar | Bounded Graph sync. |
| links discover | Resolve attachments/files/source links. |
| files ingest | Download/parse eligible files. |
| actions extract/list | Extract and view local action register. |
| brief generate | Generate Daily Brief with dry-run. |
| search | Source-linked retrieval. |
| run morning | Full morning workflow. |
| automation install-launchd/uninstall-launchd/kickstart | LaunchAgent management. |

## launchd

- User LaunchAgent.
- `StartCalendarInterval` 5:00 AM.
- App-level catch-up-after-wake using `assistant_runs` ledger.
- Weekends manual-only.
- Explicit stdout/stderr log paths.
- No dependence on shell profile.

See `resources/launchd.plist.example`.
