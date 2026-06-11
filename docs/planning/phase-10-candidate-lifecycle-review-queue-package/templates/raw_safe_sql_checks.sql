-- Raw-safe SQL checks. Counts and column/table metadata only.

PRAGMA user_version;

SELECT version, name, applied_at
FROM schema_migrations
ORDER BY version DESC
LIMIT 20;

SELECT 'daily_brief_action_candidates' AS table_name, COUNT(*) AS row_count FROM daily_brief_action_candidates
UNION ALL SELECT 'candidate_source_refs', COUNT(*) FROM candidate_source_refs
UNION ALL SELECT 'daily_brief_source_refs', COUNT(*) FROM daily_brief_source_refs
UNION ALL SELECT 'follow_up_watch_items', COUNT(*) FROM follow_up_watch_items
UNION ALL SELECT 'task_candidates', COUNT(*) FROM task_candidates
UNION ALL SELECT 'commitment_candidates', COUNT(*) FROM commitment_candidates
UNION ALL SELECT 'accepted_tasks', COUNT(*) FROM accepted_tasks
UNION ALL SELECT 'accepted_commitments', COUNT(*) FROM accepted_commitments
UNION ALL SELECT 'candidate_review_events', COUNT(*) FROM candidate_review_events
UNION ALL SELECT 'construction_project_identity', COUNT(*) FROM construction_project_identity
UNION ALL SELECT 'construction_project_keyword_registry', COUNT(*) FROM construction_project_keyword_registry
UNION ALL SELECT 'construction_project_source_matches', COUNT(*) FROM construction_project_source_matches
UNION ALL SELECT 'raw_content_access_events', COUNT(*) FROM raw_content_access_events
UNION ALL SELECT 'email_raw_message_structured', COUNT(*) FROM email_raw_message_structured
UNION ALL SELECT 'email_raw_thread_structured', COUNT(*) FROM email_raw_thread_structured
UNION ALL SELECT 'email_raw_thread_messages_structured', COUNT(*) FROM email_raw_thread_messages_structured;

SELECT 'task_candidates_review_status' AS metric, review_status, COUNT(*)
FROM task_candidates
GROUP BY review_status
UNION ALL
SELECT 'commitment_candidates_review_status', review_status, COUNT(*)
FROM commitment_candidates
GROUP BY review_status;

SELECT 'daily_brief_by_section' AS metric, section, COUNT(*)
FROM daily_brief_action_candidates
GROUP BY section;

SELECT 'candidate_source_refs_by_type' AS metric, candidate_type, COUNT(*)
FROM candidate_source_refs
GROUP BY candidate_type;

SELECT 'accepted_task_source_ref_coverage' AS metric,
       COUNT(*) AS accepted_count,
       SUM(CASE WHEN EXISTS (
           SELECT 1 FROM candidate_source_refs r
           WHERE r.candidate_type='task' AND r.candidate_id=accepted_tasks.candidate_id
       ) THEN 1 ELSE 0 END) AS source_linked
FROM accepted_tasks;

SELECT 'accepted_commitment_source_ref_coverage' AS metric,
       COUNT(*) AS accepted_count,
       SUM(CASE WHEN EXISTS (
           SELECT 1 FROM candidate_source_refs r
           WHERE r.candidate_type='commitment' AND r.candidate_id=accepted_commitments.candidate_id
       ) THEN 1 ELSE 0 END) AS source_linked
FROM accepted_commitments;

