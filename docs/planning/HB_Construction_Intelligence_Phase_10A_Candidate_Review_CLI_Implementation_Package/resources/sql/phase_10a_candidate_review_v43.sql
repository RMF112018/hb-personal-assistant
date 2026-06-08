-- Phase 10A Candidate Review CLI - V43 additive migration reference
-- Repository migrator remains authoritative; do not apply this file directly unless using it as a checked reference.

ALTER TABLE task_candidates ADD COLUMN snoozed_until_utc TEXT;
ALTER TABLE task_candidates ADD COLUMN reviewed_utc TEXT;
ALTER TABLE task_candidates ADD COLUMN reviewed_by TEXT;
ALTER TABLE task_candidates ADD COLUMN review_note_redacted TEXT;

ALTER TABLE commitment_candidates ADD COLUMN snoozed_until_utc TEXT;
ALTER TABLE commitment_candidates ADD COLUMN reviewed_utc TEXT;
ALTER TABLE commitment_candidates ADD COLUMN reviewed_by TEXT;
ALTER TABLE commitment_candidates ADD COLUMN review_note_redacted TEXT;

ALTER TABLE candidate_review_events ADD COLUMN changes_json_redacted TEXT;
ALTER TABLE candidate_review_events ADD COLUMN snoozed_until_utc TEXT;
ALTER TABLE candidate_review_events ADD COLUMN reviewer_ref TEXT;

CREATE INDEX IF NOT EXISTS ix_task_candidates_review_snooze
ON task_candidates(review_status, snoozed_until_utc, created_utc);

CREATE INDEX IF NOT EXISTS ix_commitment_candidates_review_snooze
ON commitment_candidates(review_status, snoozed_until_utc, created_utc);

CREATE INDEX IF NOT EXISTS ix_candidate_review_events_candidate
ON candidate_review_events(candidate_type, candidate_id, created_utc);
