# 03 — Deterministic Extractor Results

Module `second_brain/local_ai/email_followup_candidate_projection.py`: metadata-only, no clock, no
model, no raw body. Reuses `score_email_task_signals` for signals and `resolve_project` for keys.

## Unit coverage (crafted structured fixtures)

`tests/test_phase_10_email_followup_candidate_projection.py` proves all seven families extract,
bounded title/reason (<=120 / <=240 / <=160), no raw sentinels in output, raw access not used by
default (`raw_access_used == False`, `raw_content_access_events` unchanged), deterministic keys stable
across runs, and direction-dependent families suppressed when owner identity is unknown.

## Real-data extraction (owner-configured, `/tmp` copy, limit 500)

generated_by_family = {"waiting_on_response": 0, "response_needed": 0, "stale_thread_nudge": 0, "user_commitment": 0, "third_party_commitment": 0, "project_action_item": 0, "time_sensitive_followup": 4}

Honest limitation: subject-only metadata is sparse (commitments/asks usually live in the body), so a
real snapshot yields mostly `time_sensitive_followup`. Body-derived families are a deliberate audited
future pass. Owner-unknown run generated 1 candidate(s) (direction
families correctly suppressed).
