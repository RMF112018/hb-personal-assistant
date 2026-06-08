# Phase 10A — Batch extract-packets command (evidence)

Date: 2026-06-08 · Local-only · Dry-run default · Capped apply · No external writeback · No raw leakage

## Deliverables

| Item | Location |
| --- | --- |
| Orchestrator | `construction/second_brain/local_ai/batch_extraction.py::run_batch_extraction` |
| Extraction-layer cap/dedup | `raw_action_intelligence.py` — `max_persist` + `existing_stable_keys` params; report `skipped_existing` + `persisted_stable_keys` |
| CLI command | `cli/second_brain.py` — `extract-packets` |
| Tests | `tests/test_phase_10a_batch_extraction.py` (14 cases) |

## Required CLI behavior — results

| # | Requirement | Result |
| --- | --- | --- |
| 1 | Defaults to dry-run | PASS (`--dry-run/--apply` default dry-run) |
| 2 | `--apply` explicit | PASS |
| 3 | `--max-persist` required with `--apply` | PASS — fail-closed exit 2 |
| 4 | `--max-persist` caps ACTUAL persisted candidates | PASS — capped in the persist loop + batch budget |
| 5 | `--limit` caps selected threads | PASS (+ `--offset`) |
| 6 | `--source email` only | PASS |
| 7 | calendar/related fail closed | PASS — `UnsupportedBatchSourceError` / exit 2 |
| 8 | `--db/--model/--profile/--provider/--timeout-seconds` | PASS — mirrors `extract-packet` |
| 9 | `--summary` aggregates with `--json` | PASS |
| 10 | `extract-packet` unchanged | PASS |

## Counters separated

produced · accepted · rejected · would_persist · persisted · skipped_existing ·
unsupported_candidate_type · no_candidates · blocked · failed. Candidate types: task · commitment ·
question · risk · other. Persistence-eligible (would_persist) tracked separately from accepted.

## Verified (mock)

| Scenario | Expectation | Result |
| --- | --- | --- |
| dry-run, 3 threads (task/commitment/question) | accepted 3, would_persist 2, unsupported 1, zero rows | PASS |
| apply `--max-persist 2`, 5 task threads | persisted 2, would_persist 5; rows review + default_extract + non-null template | PASS |
| apply `--max-persist 1` | persisted ≤ 1 | PASS |
| re-apply same thread | persisted 0, skipped_existing 1, no duplicate rows | PASS |
| question candidate | accepted, visible in results, not persisted, unsupported_candidate_type 1 | PASS |
| invalid `src_9` | in source_alias_failures + top_rejection_reasons; not persisted; batch continues | PASS |
| apply guard columns | sum 0 on task_candidates + candidate_source_refs | PASS |
| source calendar/related | fail closed | PASS |
| artifact | written to artifact_dir, path in payload, no raw body text | PASS |
| offset selection | longest-first ordering honored | PASS |
| CLI apply w/o max-persist | exit 2 `apply_requires_max_persist` | PASS |
| CLI unsupported source | exit 2 `unsupported_source` | PASS |
| CLI dry-run default | applied False, summary present, zero writes | PASS |

## Validation

```
compileall src tests …………………………………………………… OK
ruff (local_ai + cli + new test) ……………………… clean for changed files
  (pre-existing: 3 B008 in cli/procore.py — unmodified, not introduced here)
mypy (raw_action_intelligence + batch_extraction) … Success
pytest — batch_extraction (14) + packet_extraction_safety + raw_action_intelligence +
  raw_model_context_packets + packet_scope + phase_10_schema + phase_08d_no_raw_access +
  phase_08d_no_writeback + second_brain_no_writeback_proof + phase_10_contracts +
  raw_extraction_hardening + local_model_readiness … all pass (134)
```

## Next recommended validation (no apply, then controlled apply)

```bash
# Dry-run 50:
hb-assistant second-brain extract-packets \
  --source email --limit 50 --dry-run --summary --db "$DB" --timeout-seconds 180 --json \
  | tee /tmp/phase10a_batch_command_dryrun_50.json

# Controlled apply (cap 10):
hb-assistant second-brain extract-packets \
  --source email --limit 50 --apply --max-persist 10 --summary --db "$DB" \
  --timeout-seconds 180 --json | tee /tmp/phase10a_batch_command_apply_10.json

# Post-apply verification:
sqlite3 "$DB" "SELECT COUNT(*) FROM task_candidates;
  SELECT recommended_next_action, model_profile_id, prompt_template_version, COUNT(*)
  FROM task_candidates GROUP BY 1,2,3;
  SELECT SUM(raw_email_body_persisted), SUM(raw_prompt_persisted), SUM(raw_response_persisted),
         SUM(external_writeback_performed), SUM(graph_writeback_performed),
         SUM(procore_writeback_performed), SUM(email_send_performed),
         SUM(calendar_mutation_performed) FROM task_candidates;"
# Expect: persisted <= 10; all recommended_next_action=review; non-null traceability; all flags 0.
```
