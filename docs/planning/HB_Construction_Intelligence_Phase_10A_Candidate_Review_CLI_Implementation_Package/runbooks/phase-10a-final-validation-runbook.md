# 14 Validation and Evidence Matrix

## Static validation

```bash
python -m compileall src tests
ruff check src/hb_assistant/construction/second_brain src/hb_assistant/cli tests
mypy src/hb_assistant/construction/second_brain
```

## Targeted pytest

```bash
pytest   tests/test_phase_10a_candidate_review.py   tests/test_phase_10a_candidate_review_cli.py   tests/test_phase_10a_batch_extraction.py   tests/test_phase_10a_packet_extraction_safety.py   tests/test_phase_10a_raw_action_intelligence.py   tests/test_phase_10_schema.py   tests/test_phase_08d_no_raw_access.py   tests/test_phase_08d_no_writeback.py   tests/test_second_brain_no_writeback_proof.py
```

## Manual command validation

```bash
export HB_PA_CONFIG=/tmp/hb-pa-dev-live.yml
export DB="$HOME/Library/Application Support/HB Personal Assistant (Dev)/db/hb-personal-assistant.sqlite"

hb-assistant second-brain review summary --db "$DB" --json
hb-assistant second-brain review list --status pending --limit 10 --db "$DB" --json
hb-assistant second-brain review show --candidate-id <id> --db "$DB" --json
hb-assistant second-brain review accept --candidate-id <id> --db "$DB" --json
hb-assistant second-brain review ignore --candidate-id <id> --reason "not actionable" --db "$DB" --json
```

## Evidence location

Write proof artifacts under `docs/evidence/construction-intelligence-phase-10a-candidate-review-cli/`.
