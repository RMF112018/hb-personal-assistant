.headers on
.mode column

SELECT 'schema_migrations_recent' AS check_name, version, name, applied_at
FROM schema_migrations
ORDER BY version DESC
LIMIT 15;

PRAGMA user_version;

SELECT 'email_message_raw_content' AS table_name, COUNT(*) AS row_count FROM email_message_raw_content;
SELECT 'email_thread_raw_context' AS table_name, COUNT(*) AS row_count FROM email_thread_raw_context;
SELECT 'email_raw_message_structured' AS table_name, COUNT(*) AS row_count FROM email_raw_message_structured;
SELECT 'email_raw_thread_structured' AS table_name, COUNT(*) AS row_count FROM email_raw_thread_structured;
SELECT 'email_raw_thread_messages_structured' AS table_name, COUNT(*) AS row_count FROM email_raw_thread_messages_structured;
SELECT 'email_raw_message_recipients_structured' AS table_name, COUNT(*) AS row_count FROM email_raw_message_recipients_structured;
SELECT 'email_raw_message_attachments_structured' AS table_name, COUNT(*) AS row_count FROM email_raw_message_attachments_structured;

SELECT 'raw_content_access_events' AS table_name, COUNT(*) AS row_count FROM raw_content_access_events;
SELECT 'email_calendar_projection_runs' AS table_name, COUNT(*) AS row_count FROM email_calendar_projection_runs;
SELECT 'email_calendar_projection_coverage' AS table_name, COUNT(*) AS row_count FROM email_calendar_projection_coverage;

SELECT 'follow_up_watch_items' AS table_name, COUNT(*) AS row_count FROM follow_up_watch_items;
SELECT 'email_followup_enrichments' AS table_name, COUNT(*) AS row_count FROM email_followup_enrichments;
SELECT 'task_candidates' AS table_name, COUNT(*) AS row_count FROM task_candidates;
SELECT 'commitment_candidates' AS table_name, COUNT(*) AS row_count FROM commitment_candidates;
SELECT 'accepted_tasks' AS table_name, COUNT(*) AS row_count FROM accepted_tasks;
SELECT 'accepted_commitments' AS table_name, COUNT(*) AS row_count FROM accepted_commitments;

SELECT 'daily_brief_action_candidates' AS table_name, COUNT(*) AS row_count FROM daily_brief_action_candidates;
SELECT 'candidate_source_refs' AS table_name, COUNT(*) AS row_count FROM candidate_source_refs;
SELECT 'daily_brief_source_refs' AS table_name, COUNT(*) AS row_count FROM daily_brief_source_refs;

SELECT 'construction_project_identity' AS table_name, COUNT(*) AS row_count FROM construction_project_identity;
SELECT 'construction_project_keyword_registry' AS table_name, COUNT(*) AS row_count FROM construction_project_keyword_registry;
SELECT 'construction_project_source_matches' AS table_name, COUNT(*) AS row_count FROM construction_project_source_matches;

SELECT 'email_structured_source_quality' AS check_name, source_quality, COUNT(*) AS row_count
FROM email_raw_message_structured
GROUP BY source_quality
ORDER BY row_count DESC;

SELECT 'thread_structured_source_quality' AS check_name, source_quality, COUNT(*) AS row_count
FROM email_raw_thread_structured
GROUP BY source_quality
ORDER BY row_count DESC;

SELECT 'email_body_ref_availability' AS check_name,
       SUM(CASE WHEN raw_email_id IS NOT NULL OR raw_row_id IS NOT NULL THEN 1 ELSE 0 END) AS body_ref_available,
       COUNT(*) AS structured_rows
FROM email_raw_message_structured;

SELECT 'thread_body_ref_availability' AS check_name,
       SUM(CASE WHEN raw_thread_context_id IS NOT NULL OR raw_row_id IS NOT NULL THEN 1 ELSE 0 END) AS body_ref_available,
       COUNT(*) AS structured_rows
FROM email_raw_thread_structured;

SELECT 'daily_brief_by_section' AS check_name, section, COUNT(*) AS row_count
FROM daily_brief_action_candidates
GROUP BY section
ORDER BY row_count DESC;

SELECT 'daily_brief_source_ref_coverage' AS check_name,
       COUNT(*) AS total_candidates,
       SUM(CASE WHEN EXISTS (
          SELECT 1 FROM candidate_source_refs r
          WHERE r.candidate_type = 'daily_brief_action'
            AND r.candidate_id = c.daily_brief_action_candidate_id
       ) THEN 1 ELSE 0 END) AS covered_candidates
FROM daily_brief_action_candidates c;

SELECT 'daily_brief_project_key_coverage' AS check_name,
       COUNT(*) AS total_candidates,
       SUM(CASE WHEN project_key IS NOT NULL AND TRIM(project_key) <> '' THEN 1 ELSE 0 END) AS project_key_candidates
FROM daily_brief_action_candidates;

-- Guard-column proof must be adapted if table/column names differ. Do not SELECT raw body/html/url fields.
