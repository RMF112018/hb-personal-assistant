# 02 Repo-Truth Audit Baseline

Repository truth must be reconfirmed before editing. This package is based on a GitHub connector audit and the current Phase 10A objective prompt.

## Observed Phase 10A implementation

- `src/hb_assistant/construction/second_brain/local_ai/batch_extraction.py` implements capped batch extraction.
- `src/hb_assistant/construction/second_brain/local_ai/raw_action_intelligence.py` implements local-model output validation, normalization, source-ref resolution, and persistence.
- Packet builders exist for bounded email-thread action packets.
- Existing tests cover batch extraction, packet extraction safety, raw action intelligence, schema, no raw access, and no writeback.
- The current working local extraction model is expected to remain `mistral-nemo:12b` through the `default_extract` profile.

## Observed CLI state

- Batch extraction is currently registered as:

```bash
hb-assistant second-brain extract-packets
```

- Do not assume it is under:

```bash
hb-assistant second-brain phase-10 extract-packets
```

- Some single-packet Phase 10 commands remain under the `phase-10` command group.
- A top-level `second-brain review` app already exists for a prior review-burden/advisory policy area. Candidate review commands must be added without breaking that existing namespace.

## Observed schema state

- Current schema head observed: `V42`.
- Phase 10 candidate tables were introduced in V41.
- V42 adds raw content related support but does not authorize raw persistence into candidate review output.

## Candidate tables observed

`task_candidates` includes candidate identity, title, assignee, due date, urgency, waiting state, safety category, confidence, reason, recommended next action, review status, model profile, prompt template version, created/updated timestamps, and guard columns.

`commitment_candidates` mirrors tasks but uses commitment-specific actor/promised fields.

`candidate_source_refs` links candidates to source refs and redacted evidence snippets.

`candidate_review_events` exists, but repo audit found a likely mismatch between current table DDL and store helper insert fields. Fix that drift before relying on event audit history.

## Critical drift to recheck locally

Before editing, run:

```bash
git status --short
git rev-parse HEAD
grep -R "def insert_candidate_review_event\|candidate_review_events" -n src tests
grep -R "review_app\|@review_app.command" -n src/hb_assistant/cli/second_brain.py
```

Stop if local repo truth materially differs from this package.
