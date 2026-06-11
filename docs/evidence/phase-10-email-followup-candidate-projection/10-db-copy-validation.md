# 10 — DB Copy Validation

- Audit root: `/tmp/hb-phase10-email-followup-candidate-projection-20260611-132651`
- Prod DB copied from the plain app-support root, **read-only**; WAL+SHM copied and checkpointed for a
  faithful snapshot. Integrity check: **ok**. Schema version (schema_migrations max): **49**.
- All apply ran only against the `/tmp` copy; prod never opened for write by the slice.
- **Prod DB sha256 identical pre/post** (`d0c3e52a...`) -> production untouched. (DBeaver held the file
  open as an external reader; the scheduler `--environment dev` process targets the Dev root.)

## Owner-unknown run (honest default)

generated=1, source-ref coverage=1.0,
idempotent=True, guard sums all 0, data-gap -> populated.

## Owner-configured run (HB_ASSISTANT_OWNER_DOMAINS=hedrickbrothers.com — 311/405 senders)

generated_by_family={"waiting_on_response": 0, "response_needed": 0, "stale_thread_nudge": 0, "user_commitment": 0, "third_party_commitment": 0, "project_action_item": 0, "time_sensitive_followup": 4}; by_section={"follow_up": 4};
dbac source-ref coverage=1.0; idempotent=True.
