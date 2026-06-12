# 01 — Ranking / Assembly Prerequisite Audit

**Status: `ranking_assembly_prerequisite_present`** → implementation proceeds at V52.

The prerequisite "Ollama-assisted feedback-calibrated candidate ranking + daily-brief assembly"
slice (V51) is present in local repo truth (HEAD `6938380b`). The telemetry slice consumes it
read-only.

## Repo-true contract this slice consumes

| Concern | Repo-true source |
|---|---|
| ranking run table | `daily_brief_ranking_runs` (`store.list_ranking_runs`) |
| ranked candidate table | `daily_brief_ranked_candidates` (`store.list_ranked_candidates`) |
| assembly run table | `daily_brief_assembly_runs` (`store.list_assembly_runs`) |
| assembly section table | `daily_brief_assembly_sections` (`store.list_assembly_sections`) |
| similarity/duplicate edges | `candidate_similarity_edges` (`store.list_similarity_edges`) |
| model ranking receipts | `local_model_run_receipts` (`store.list_local_model_run_receipts`) |
| policy version field | `daily_brief_ranking_runs.policy_version` (`rank-policy-v1`) |
| feedback calibration identity | `daily_brief_ranking_runs.feedback_digest_hash` |
| deterministic/feedback/model/final scores | `daily_brief_ranked_candidates.{deterministic,feedback,model_advisory,final}_score` |
| candidate set hash | `daily_brief_ranking_runs.candidate_set_hash` |
| model degradation/withheld/fallback | `daily_brief_ranking_runs.{model_status,degraded_reason,deterministic_fallback_used}` |
| lifecycle disposition | `candidate_lifecycle_read_model.build_review_queue` + `candidate_lifecycle_events` |
| source-ref coverage | `candidate_source_refs` count per candidate (via review queue) |

## Join key discipline

V51 persists the namespaced review-queue candidate id (`candidate_ranking_packets._candidate_id`) as
`daily_brief_action_candidate_id`. V52 rebuilds the same review queue (`include_hidden=True`) and
joins on that id; outcomes are matched to lifecycle events by `(subject_type, subject_id)`. Candidate
identity is never inferred from raw titles.
