# Final Addendum Evidence Schema

Use this structure for `final-addendum-closeout-proof.json`.

```json
{
  "status": "ACCEPTED | CONDITIONALLY_ACCEPTED_WITH_EXTERNAL_BLOCKER | NOT_ACCEPTED",
  "timestamp": "ISO-8601",
  "commit": "git sha",
  "gates": {
    "pytest": {"pass": true, "exit_code": 0, "evidence": "..."},
    "ruff": {"pass": true, "exit_code": 0, "evidence": "..."},
    "mypy": {"pass": true, "exit_code": 0, "evidence": "..."},
    "auth_status": {"pass": true, "exit_code": 0, "evidence": "..."},
    "diagnostics_paths": {"pass": true, "exit_code": 0, "evidence": "..."},
    "graph_safe": {"pass": true, "exit_code": 0, "evidence": "..."},
    "delegated_graph_proof": {
      "pass": true,
      "external_blocker": false,
      "exit_code": 0,
      "evidence": "..."
    },
    "files_ingest_dry_run": {"pass": true, "exit_code": 0, "evidence": "..."},
    "run_morning_dry_run": {"pass": true, "exit_code": 0, "evidence": "..."}
  },
  "blockers": [],
  "redaction_confirmation": true
}
```

Do not include raw secrets, token values, PEM bodies, full email bodies, or full file contents.
