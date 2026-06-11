# Join Path Contract

## Required Join Map

The local code agent must write a repo-true join map before coding:

```text
ranking run -> ranked candidate -> daily_brief_action_candidate_id -> candidate_source_refs
ranking run -> assembly run/section -> section_key/group_key -> ranked candidates
ranked candidate -> lifecycle subject (daily_brief_action or mapped domain subject)
lifecycle subject -> candidate_lifecycle_events / candidate_review_events / accepted_* / follow_up_watch_items
ranked candidate -> model receipt/profile metadata
ranked candidate/group -> similarity/duplicate edge metadata
ranked candidate -> source family / candidate family / project_key
```

## Required Fallbacks

- If no ranked rows exist: `no_ranked_briefs`.
- If no assembly rows exist but ranked rows exist: evaluate ranking-only and mark `assembly_data_missing`.
- If no lifecycle events/outcomes exist: mark `insufficient_outcome_data`; do not infer success.
- If model receipts are missing: evaluate deterministic-only and mark `model_telemetry_missing`.
- If source refs are missing for surfaced actionable items: fail/degrade according to source-ref gate contract.

## Candidate ID Discipline

Do not infer candidate identity from raw titles. Use stable candidate IDs, group keys, source-ref hashes, and repo-provided derivation helpers.
