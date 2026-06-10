# Final Output Manifest — Scheduler / Daily-Run Reliability

## Intended operator-facing output

A redacted daily-run **status file** whose `run_summary` block tells Bobby at a glance: the result
(success / degraded / partial / failure / skipped), when it started and completed, where the latest
and last-good briefs are, per-stage receipts, a safe error summary, and that the browser was not
auto-opened — plus a safe, dry-run scheduler install preview and plist.

## Generated proof artifacts

| Artifact | Path | From | Safe? |
|---|---|---|---|
| Scheduler install preview | `01-scheduler-install-preview-final-output.txt` | `preview_install()` (home redacted) | yes |
| Scheduler status | `02-scheduler-status-final-output.json` | `status()` (home redacted) | yes |
| Success status | `03-success-status-proof.json` | seeded apply run | yes |
| Degraded status | `04-degraded-status-proof.json` | bogus-profile run | yes |
| Failure status | `05-failure-status-proof.json` | fail-closed guard + summary | yes |
| Last-success preservation | `06-last-success-preservation-proof.md` | two-run sequence | yes |
| Stable output path | `07-stable-output-path-proof.md` | path policy + flags | yes |
| Launchd plist preview | `08-launchd-plist-preview.plist` | `render_plist()` (home redacted) | yes |
| Safety scan | `09-safety-scan-results.txt` | scan | yes (0 findings) |
| Production DB unchanged | `10-production-db-unchanged-proof.txt` | sha256 | yes (unchanged) |

## Manual verification command

```bash
hb-assistant second-brain daily-run scheduler install            # dry-run preview (no write)
hb-assistant second-brain daily-run run --as-of 2026-06-09T05:00:00-04:00 --apply \
  --no-synthesize --db /tmp/copy.sqlite --status-dir /tmp/st --browser-output-dir /tmp/html
cat /tmp/st/latest-status.json   # inspect run_summary
```
