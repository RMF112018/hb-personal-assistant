# Reference — Existing Code Surfaces To Reuse

Reuse before creating new abstractions.

## Email/calendar projection

- `hb_assistant.construction.email_calendar.projection_engine.status`
- `hb_assistant.construction.email_calendar.projection_engine.coverage`
- `hb_assistant.construction.email_calendar.projection_engine.reprocess`
- `hb_assistant.construction.email_calendar.projection_registry`
- `hb_assistant.construction.email_calendar.schema`
- `hb_assistant.construction.email_calendar.read_models`
- `hb_assistant.cli.email_calendar`

## Candidate persistence and gates

- `hb_assistant.construction.second_brain.local_ai.daily_brief_candidate_writer.persist_candidate_with_refs`
- `hb_assistant.construction.second_brain.local_ai.daily_brief_candidate_writer.candidate_source_ref_coverage`
- `hb_assistant.construction.second_brain.local_ai.source_ref_gate.gate_model_candidate_context`
- `hb_assistant.construction.second_brain.local_ai.source_ref_gate.executive_coverage_ok`

## Calendar

- `hb_assistant.construction.second_brain.local_ai.calendar_prep.build_calendar_prep_candidates`
- `calendar_category.resolve_calendar_category`
- `calendar_classify.classify_calendar_event`
- `project_aliases.resolve_project`

## Procore

- `hb_assistant.construction.second_brain.local_ai.procore_digest.build_procore_action_digest`
- `hb_assistant.construction.second_brain.local_ai.procore_ranking.rank_procore_signals`
- `hb_assistant.procore.projection_engine`
- `hb_assistant.procore.projection_audit`

## Daily brief context/status

- `hb_assistant.construction.second_brain.local_ai.daily_brief_context_packet.build_daily_brief_context_packet`
- Daily-run CLI/orchestrator modules found by `rg "daily-run|daily_run|build_daily_brief_context_packet|source_ref_gate|data_gaps" src/hb_assistant`.
