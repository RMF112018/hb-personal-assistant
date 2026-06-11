# Scope Lock — Daily Brief Raw Projection First Slice

## Mission

Implement only the first slice needed to convert the new raw/projection substrate into an operator-useful daily brief:

- Activate V49 email/calendar projection.
- Persist source-linked calendar and Procore daily-brief candidates.
- Improve deterministic project identity/project-key resolution without unsafe automation.
- Enforce source-ref/usefulness/contradiction gates.
- Surface empty email/follow-up layers as data gaps.

## Do not expand into these areas

- Do not build a full email NLP follow-up extraction system unless the current code already has a safe candidate writer and it is required to pass the data-gap/status acceptance criteria.
- Do not add cloud LLM routes.
- Do not add writeback.
- Do not mutate email/calendar/Procore/Graph data.
- Do not add raw content to Obsidian, evidence, committed fixtures, browser proof, JSON proof, or status output.
- Do not rewrite the entire daily brief pipeline.
- Do not replace existing V49/Procore projection architecture if small integration changes satisfy the objective.

## Implementation posture

Prefer small, composable integration layers around existing code:

- `hb_assistant.construction.email_calendar.projection_engine`
- `hb_assistant.construction.email_calendar.read_models`
- `hb_assistant.construction.second_brain.local_ai.calendar_prep`
- `hb_assistant.construction.second_brain.local_ai.procore_digest`
- `hb_assistant.construction.second_brain.local_ai.daily_brief_candidate_writer`
- `hb_assistant.construction.second_brain.local_ai.source_ref_gate`
- `hb_assistant.construction.second_brain.local_ai.daily_brief_context_packet`

Add new abstractions only where they reduce coupling or make gates testable.
