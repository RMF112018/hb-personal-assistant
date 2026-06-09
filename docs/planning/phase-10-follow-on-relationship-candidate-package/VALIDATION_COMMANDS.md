# Validation Commands

Use repo-truth command names if they differ.

## Branch / Git

```bash
cd /Users/bobbyfetting/hb-personal-assistant

git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git status --short
git branch --contains HEAD
git rev-parse main
git log --oneline --decorate -n 20
```

## Tests

```bash
python -m pytest   tests/test_phase_10_acceptance_promotion.py   tests/test_phase_10_follow_up_monitor.py   tests/test_phase_10_procore_digest.py   tests/test_phase_10_daily_brief_synthesis.py   tests/test_phase_10_calendar_meeting_prep.py   tests/test_phase_10_daily_brief_rendering.py   tests/test_phase_10_pipeline.py   tests/test_agent_registry.py   tests/test_second_brain_agents_cli.py   tests/test_phase_10_relationship_candidates.py
```

## Lint / Format / Types

```bash
ruff check src/hb_assistant/construction/second_brain/local_ai tests
ruff format --check src/hb_assistant/construction/second_brain/local_ai tests
mypy src/hb_assistant/construction/second_brain/local_ai
```

If the repository standard uses a broader command, run that too. Document unrelated pre-existing failures rather than hiding them.

## Schema Status

```bash
hb-assistant construction second-brain phase-10 schema-status --db <copy.sqlite> --json
```

## Relationship Candidate CLI Proof

```bash
hb-assistant construction second-brain relationship-candidates scan   --db /tmp/hb_relationship_candidate_proof.sqlite   --as-of 2026-06-09T05:00:00+00:00   --limit 25   --scan-threads 50   --scan-events 50   --dry-run   --summary   --json

hb-assistant construction second-brain relationship-candidates scan   --db /tmp/hb_relationship_candidate_proof.sqlite   --as-of 2026-06-09T05:00:00+00:00   --apply   --max-persist 5   --summary   --json

hb-assistant construction second-brain relationship-candidates scan   --db /tmp/hb_relationship_candidate_proof.sqlite   --as-of 2026-06-09T05:00:00+00:00   --apply   --max-persist 5   --summary   --json
```

## SQLite Proof Queries

Adjust columns to repo truth:

```sql
SELECT COUNT(*) FROM phase10_relationship_candidates;

-- Guard columns should sum to zero.
SELECT
  COALESCE(SUM(raw_email_body_persisted),0) +
  COALESCE(SUM(raw_document_text_persisted),0) +
  COALESCE(SUM(raw_calendar_payload_persisted),0) +
  COALESCE(SUM(raw_procore_payload_persisted),0) +
  COALESCE(SUM(raw_prompt_persisted),0) +
  COALESCE(SUM(raw_response_persisted),0) +
  COALESCE(SUM(signed_url_persisted),0) +
  COALESCE(SUM(download_url_persisted),0) +
  COALESCE(SUM(external_writeback_performed),0) +
  COALESCE(SUM(graph_writeback_performed),0) +
  COALESCE(SUM(procore_writeback_performed),0) +
  COALESCE(SUM(email_send_performed),0) +
  COALESCE(SUM(calendar_mutation_performed),0) AS guard_sum
FROM phase10_relationship_candidates;
```

## Daily Brief Proof

```bash
hb-assistant construction second-brain daily-brief render   --db /tmp/hb_relationship_candidate_proof.sqlite   --date 2026-06-09   --limit 50   --json
```

## Pipeline Regression

```bash
hb-assistant construction second-brain pipeline run   --db /tmp/hb_relationship_candidate_proof.sqlite   --as-of 2026-06-09T05:00:00+00:00   --dry-run   --json
```

