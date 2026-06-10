# Manual Verification Runbook — Phase 10 Full Candidate Implementation

Run from the repo root inside the venv (`source .venv/bin/activate`, Python 3.12). All commands are
read-only / dry-run and safe. Use a disposable DB copy for any `--db` example:
`cp "$(hb-assistant ...path...)" /tmp/copy.sqlite` or any temp path.

## Branch + baseline
```bash
git checkout experiment/phase-10-full-candidate-implementation
git log --oneline main..HEAD          # 10 commits (1 setup + 9 candidates)
git status --short                    # clean (ignore concurrent foreign evidence churn)
```

## Per-candidate operator surfaces
```bash
# 01 Daily Brief convergence (pending V45 section in browser/Obsidian/status)
hb-assistant second-brain daily-run run --as-of 2026-06-09T05:00:00-04:00 --no-synthesize \
  --with-email-raw-enrichment --json --db /tmp/copy.sqlite

# 02 Candidate review report
hb-assistant second-brain review report --db /tmp/copy.sqlite --no-json

# 03 Follow-up watch report
hb-assistant second-brain follow-up-watch report --db /tmp/copy.sqlite --as-of 2026-06-09T00:00:00+00:00 --no-json

# 04 Scheduler install preview + daily-run status (run_summary)
hb-assistant second-brain daily-run scheduler install     # dry-run preview, no write

# 05 Local model routing diagnostics
hb-assistant second-brain local-model diagnostics --no-json        # or --mock offline

# 06 Procore monitoring read-model
hb-assistant procore live monitor --db /tmp/copy.sqlite --no-json

# 07 Relationship / entity report
hb-assistant second-brain relationship-candidates report --db /tmp/copy.sqlite --no-json

# 08 Hardened MCP context packet
hb-assistant second-brain daily-brief mcp-packet --db /tmp/copy.sqlite --as-of 2026-06-09T05:00:00-04:00 --no-json

# 09 Document/file parse read-model
hb-assistant files parse-index \
  docs/evidence/phase-10-full-candidate-implementation/09-document-file-parsing/fixtures/note.txt --no-json
```

## Validation
```bash
python -m compileall src tests
# Per-candidate targeted suites (all green):
pytest -q tests/test_phase_10_daily_run_pending_followup_convergence.py \
          tests/test_phase_10_candidate_review_report.py \
          tests/test_phase_10_follow_up_watch_report.py \
          tests/test_phase_10_daily_run_reliability.py \
          tests/test_phase_10_model_routing_diagnostics.py \
          tests/test_phase_10_procore_monitor.py \
          tests/test_phase_10_relationship_entity_report.py \
          tests/test_phase_10_mcp_packet_hardening.py \
          tests/test_phase_10_file_parse_read_model.py
ruff check <changed-module>      # each changed module is clean
mypy <changed-module>            # each changed module is clean
```

## Regenerate evidence (temp DBs only; production proven unchanged)
The `/tmp/gen_evidence_0N.py` generators were used to produce each candidate's evidence; re-running
them rebuilds the artifacts on disposable temp DBs and re-proves the production DB checksum unchanged.
