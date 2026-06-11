# Reference — Repo Truth Targets

Inspect current repo truth before coding.

## Required commands

```bash
cd /Users/bobbyfetting/hb-personal-assistant
git fetch origin
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git status --short
git branch --contains HEAD
git rev-parse main
git rev-parse origin/main
git show --stat --oneline --decorate 4d8ca0717324955dab539ebf0690b5a93d4db6e0
git log --oneline --decorate --graph -40 --all
```

## Required searches

```bash
rg -n "LATEST_SCHEMA_VERSION|V46|V47|V48|V49|email_calendar|projection-reprocess|projection_coverage|daily_brief_action_candidates|candidate_source_refs|build_calendar_prep_candidates|build_procore_action_digest|gate_model_candidate_context|usefulness|contradiction|data_gaps|project_alias|construction_project_identity" src tests docs
```

## Current known code surfaces from commit `4d8ca0717...`

- `src/hb_assistant/store/migrator.py`
- `src/hb_assistant/construction/email_calendar/projection_registry.py`
- `src/hb_assistant/construction/email_calendar/projection_engine.py`
- `src/hb_assistant/construction/email_calendar/read_models.py`
- `src/hb_assistant/construction/email_calendar/schema.py`
- `src/hb_assistant/cli/email_calendar.py`
- `src/hb_assistant/construction/second_brain/local_ai/daily_brief_candidate_writer.py`
- `src/hb_assistant/construction/second_brain/local_ai/source_ref_gate.py`
- `src/hb_assistant/construction/second_brain/local_ai/calendar_prep.py`
- `src/hb_assistant/construction/second_brain/local_ai/procore_digest.py`
- `src/hb_assistant/construction/second_brain/local_ai/procore_ranking.py`
- `src/hb_assistant/construction/second_brain/local_ai/daily_brief_context_packet.py`
