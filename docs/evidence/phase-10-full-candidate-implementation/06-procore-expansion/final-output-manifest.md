# Final Output Manifest — Procore Expansion

## Intended operator-facing output

`procore live monitor`: one consolidated, read-only Procore monitoring read-model for daily-brief
intelligence — endpoint contract status (live-verified vs degraded), per-project source-refresh health
(current/stale/never), next operator action for stale endpoints, and a degraded-honest per-project +
overall verdict (healthy / partial_stale / stale / no_data). No live HTTP call, no writeback.

## Generated proof artifacts

| Artifact | Path | From | Safe? |
|---|---|---|---|
| Monitoring read-model (MD) | `01-procore-digest-final-output.md` | seeded temp DB | yes |
| Monitoring read-model (JSON) | `02-procore-digest-final-output.json` | seeded temp DB | yes |
| Source-refresh status | `03-source-refresh-status-proof.json` | report verdicts | yes |
| Endpoint contract | `04-endpoint-contract-proof.md` | registry | yes |
| Sync persistence | `05-sync-persistence-proof.json` | seeded watermark | yes |
| Daily-brief consumption | `06-daily-brief-consumption-proof.md` | digest + monitor | yes |
| Degraded endpoint | `07-degraded-endpoint-proof.md` | unverified + no_data | yes |
| No-writeback | `08-no-writeback-proof.txt` | counts before/after | yes |
| Safety scan | `09-safety-scan-results.txt` | scan | yes (0 findings) |
| Production DB unchanged | `10-production-db-unchanged-proof.txt` | sha256 | yes (unchanged) |

## Manual verification command

```bash
hb-assistant procore live monitor --db /tmp/copy.sqlite --no-json     # Markdown monitoring report
hb-assistant procore live monitor --project <key> --json
```
