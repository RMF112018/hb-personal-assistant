# Final Output Manifest — Follow-up Watch Quality

## Intended operator-facing output

`second-brain follow-up-watch report`: a deterministic, review-safe report grouping accepted
tasks/commitments by **operator action** — needs Bobby action, waiting on someone else, stale / no
response, monitor only, closed / resolved, and needs review / insufficient evidence. Each item is
source-linked and carries watch status, reason/quality codes, actionability, and staleness metadata.
JSON default; Markdown via `--no-json` / `--markdown-out`. No model, no writeback, persists nothing.

## Generated proof artifacts

| Artifact | Path | Generated from | Safe to commit? |
|---|---|---|---|
| Watch report (Markdown) | `01-followup-watch-final-output.md` | temp DB, synthetic | yes |
| Watch report (JSON) | `02-followup-watch-final-output.json` | temp DB, synthetic | yes |
| Stale proof | `03-stale-followup-proof.json` | aged item | yes |
| Closed-loop proof | `04-closed-loop-proof.json` | terminal status | yes |
| Waiting/needs-review proof | `05-waiting-state-proof.json` | mixed states | yes |
| Model-unavailable proof | `06-model-unavailable-proof.md` | repeat build | yes |
| Daily-brief consumption | `07-daily-brief-consumption-proof.md` | analysis | yes |
| Safety scan | `08-safety-scan-results.txt` | scan | yes (0 findings) |
| Guard-column proof | `09-guard-column-proof.json` | scan --apply temp DB | yes (sum 0) |
| Production DB unchanged | `10-production-db-unchanged-proof.txt` | sha256 | yes (unchanged) |

## Manual verification command

```bash
hb-assistant second-brain follow-up-watch report --db /tmp/copy.sqlite --as-of 2026-06-09T00:00:00+00:00 --no-json
```
