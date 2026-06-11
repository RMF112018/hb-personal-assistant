# 02 — Email Follow-Up Domain Contract

See `docs/architecture/phase-10-email-followup-candidate-projection.md` for the full design record.

| Family | Section | Domain table | Confidence floor |
|---|---|---|---:|
| waiting_on_response | waiting | task_candidates | 0.55 |
| response_needed | follow_up | task_candidates | 0.65 |
| stale_thread_nudge | follow_up | task_candidates | 0.55 |
| user_commitment | actions | commitment_candidates | 0.70 |
| third_party_commitment | waiting | commitment_candidates | 0.70 |
| project_action_item | actions | task_candidates | 0.55 |
| time_sensitive_followup | follow_up | task_candidates | 0.55 |

A first-person promise -> commitment; an ask awaiting reply -> waiting/response. Routine sent mail with
no promise and no ask produces no candidate. Every daily-brief row goes through
`persist_candidate_with_refs` (hashed source ref, 100% coverage). `follow_up_watch_items` is not a
projection target (post-acceptance monitor only).
