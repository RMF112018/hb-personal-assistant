# 05 — Artifact-selection proof

- source_file_lookup → `source_connector` target (route only; no live read).
- research_answer → answer_drafts when draft_id exists; research_packets when only packet_id.
- ask_second_brain → prefers draft_id, then packet_id, then projection_id; else insufficient_context.
- open_loop_triage → open_loops + review effective-state (read only; no task creation).
- decision_preference_lookup → decision_memory (get_decision / get_preference).
- draft_review → inspects draft/packet header + sections; preserves review labels + bounded citations
  + source refs; flags no-citation / candidate-content / excluded-content warnings.
- meeting_prep / daily_brief_context / project_intelligence_context → route to supplied context
  artifacts; mark implementation deferred to N8C-17.

Only bounded, whitelisted scalar metadata is copied (ids/types/status/title/counts/labels). Every
`*_json` blob and nested payload is dropped. Tests: `test_research_answer_*`, `test_ask_prefers_*`,
`test_open_loop_triage_*`, `test_decision_preference_*`, `test_draft_review_*`, `test_meeting_prep_*`,
`test_envelope_carries_no_raw_bodies_or_payloads`.
