# 08 — Commitment Test Failure Resolution

## Failure (deterministic, offline)

`tests/test_phase_10_email_task_extraction.py::test_commitment_persists_to_commitment_table` failed
with persisted == 0, rejected == 1, reason "assignee_waiting_state_inconsistent". Fully offline
(StaticOutputClient) — NOT model-dependent.

## Root cause

The fixture inherited assignee="user" while overriding waiting_state="waiting_on_others" on a
non-follow-up title. The deliberate coherence rule in `raw_action_intelligence.py`
(assignee=="user" and waiting=="waiting_on_others" and not is_followup -> reject) correctly rejects
this incoherent combination. The fixture was wrong; the rule is correct.

## Resolution (fixture fixed; rule unchanged)

Fixture corrected to a coherent third-party commitment (assignee="other"), preserving the routing
intent. Coherence rule left unchanged. Added regressions:

1. test_commitment_persists_to_commitment_table — third-party commitment -> commitment_candidates.
2. test_user_commitment_persists_to_commitment_table — user commitment -> commitment_candidates.
3. test_incoherent_assignee_waiting_state_still_rejected — original incoherent combo STILL rejected.

All pass. The new slice additionally proves user/third-party commitment candidates persist to
commitment_candidates with source refs and reach the brief.
