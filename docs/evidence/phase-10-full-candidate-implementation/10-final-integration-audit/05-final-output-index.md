# Final Output Index — operator-facing artifacts per candidate

| # | Candidate | New operator surface | Final-output artifacts |
|---|---|---|---|
| 01 | Daily Brief Surface Convergence | V45 pending section in daily-run browser HTML + Obsidian + status | `03-browser-final-output.html`, `04-obsidian-final-output.md`, `05-status-final-output.json` |
| 02 | Candidate Review UX | `second-brain review report` | `01-review-list-final-output.md`, `03-review-export-final-output.json`, `05-apply-cap-proof.json` |
| 03 | Follow-up Watch Quality | `second-brain follow-up-watch report` | `01/02-followup-watch-final-output.{md,json}` |
| 04 | Scheduler Reliability | daily-run status `run_summary` + scheduler preview | `02-scheduler-status-final-output.json`, `03/04/05-*-status-proof.json`, `08-launchd-plist-preview.plist` |
| 05 | Local Model Routing | `second-brain local-model diagnostics` | `01/02-routing-diagnostics-final-output.{json,md}`, `03-eval-summary-final-output.json` |
| 06 | Procore Expansion | `procore live monitor` | `01/02-procore-digest-final-output.{md,json}` |
| 07 | Relationship / Entity | `second-brain relationship-candidates report` | `01/02-relationship-candidates-final-output.{md,json}` |
| 08 | MCP Context Packet | `second-brain daily-brief mcp-packet` | `01/02-mcp-packet-final-output.{json,md}` |
| 09 | Document / File Parsing | `hb-assistant files parse-index` | `01/02-file-parse-final-output.{md,json}` |

All artifacts are synthetic/sanitized and safe to commit; each candidate's `final-output-manifest.md`
gives the manual verification command.
