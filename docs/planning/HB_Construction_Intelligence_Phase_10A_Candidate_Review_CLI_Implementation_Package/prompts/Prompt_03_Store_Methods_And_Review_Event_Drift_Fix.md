# Prompt 03 — Store Methods and Review Event Drift Fix

## Objective

Add store-layer candidate read/update methods and fix the observed `candidate_review_events` schema/helper drift.


## Repo-truth baseline

- Repository: `RMF112018/hb-personal-assistant`
- Current audited schema head: `V42`; local agent must rebaseline.
- Target update: Phase 10A Candidate Review CLI.
- Current batch command path observed: `hb-assistant second-brain extract-packets`.
- Review workflow must operate only on persisted local candidate rows.
- Local dirty state and exact HEAD are not verifiable from this package; run `git status --short` and `git rev-parse HEAD` before editing.

Repository truth is authoritative. Stop and report if the local repo materially differs from this package.

## Global guardrails

- No email send.
- No calendar mutation.
- No Graph writeback.
- No Procore writeback.
- No external/cloud LLM dependency.
- No raw email body, raw document text, raw calendar payload, raw Procore payload, raw prompt, raw response, signed URL, download URL, token, or secret persistence/output.
- Do not broaden packet extraction scope.
- Do not alter Phase 10A extraction prompt/model/stable-key behavior unless a test failure proves a direct compatibility issue.
- Review actions are local DB updates only.


## Files likely affected

- `src/hb_assistant/construction/store/repositories.py`
- `tests/test_phase_10a_candidate_review.py`

## Required methods

Add `get_task_candidate`, `get_commitment_candidate`, `get_candidate`, `list_review_candidates`, `update_candidate_review_state`, `update_candidate_fields`, `insert_candidate_review_event`, and a candidate-specific source refs helper if needed.

## Drift fix

Make `insert_candidate_review_event` match the actual DDL: `review_event_id`, `candidate_type`, `candidate_id`, `action`, `prior_status`, `new_status`, `user_note_redacted`, `created_utc`, plus V43 fields if present. Do not silently swallow event insert failures.
