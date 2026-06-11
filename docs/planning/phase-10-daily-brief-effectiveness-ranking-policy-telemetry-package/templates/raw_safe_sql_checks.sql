-- Phase 10 Daily Brief Effectiveness Telemetry raw-safe validation helpers.
-- Run against a /tmp DB copy only.

.headers on
.mode column

SELECT 'schema_version' AS check_name, MAX(version) AS value FROM schema_migrations;

SELECT 'daily_brief_exposure_events_present' AS check_name, COUNT(*) AS value
FROM sqlite_master WHERE type='table' AND name='daily_brief_exposure_events';
SELECT 'daily_brief_item_outcome_events_present' AS check_name, COUNT(*) AS value
FROM sqlite_master WHERE type='table' AND name='daily_brief_item_outcome_events';
SELECT 'ranking_policy_eval_runs_present' AS check_name, COUNT(*) AS value
FROM sqlite_master WHERE type='table' AND name='ranking_policy_eval_runs';
SELECT 'ranking_policy_eval_items_present' AS check_name, COUNT(*) AS value
FROM sqlite_master WHERE type='table' AND name='ranking_policy_eval_items';
SELECT 'model_profile_eval_results_present' AS check_name, COUNT(*) AS value
FROM sqlite_master WHERE type='table' AND name='model_profile_eval_results';
SELECT 'brief_effectiveness_rollups_present' AS check_name, COUNT(*) AS value
FROM sqlite_master WHERE type='table' AND name='brief_effectiveness_rollups';

-- Guard sums. Keep column list aligned with repo-true PHASE_10_GUARD_COLUMNS.
WITH guard_sums AS (
  SELECT 'daily_brief_exposure_events' AS table_name,
    COALESCE(SUM(raw_email_body_persisted),0)+COALESCE(SUM(raw_document_text_persisted),0)+COALESCE(SUM(raw_calendar_payload_persisted),0)+COALESCE(SUM(raw_procore_payload_persisted),0)+COALESCE(SUM(raw_prompt_persisted),0)+COALESCE(SUM(raw_response_persisted),0)+COALESCE(SUM(signed_url_persisted),0)+COALESCE(SUM(download_url_persisted),0)+COALESCE(SUM(external_writeback_performed),0)+COALESCE(SUM(graph_writeback_performed),0)+COALESCE(SUM(procore_writeback_performed),0)+COALESCE(SUM(email_send_performed),0)+COALESCE(SUM(calendar_mutation_performed),0) AS guard_sum
  FROM daily_brief_exposure_events
  UNION ALL SELECT 'daily_brief_item_outcome_events',
    COALESCE(SUM(raw_email_body_persisted),0)+COALESCE(SUM(raw_document_text_persisted),0)+COALESCE(SUM(raw_calendar_payload_persisted),0)+COALESCE(SUM(raw_procore_payload_persisted),0)+COALESCE(SUM(raw_prompt_persisted),0)+COALESCE(SUM(raw_response_persisted),0)+COALESCE(SUM(signed_url_persisted),0)+COALESCE(SUM(download_url_persisted),0)+COALESCE(SUM(external_writeback_performed),0)+COALESCE(SUM(graph_writeback_performed),0)+COALESCE(SUM(procore_writeback_performed),0)+COALESCE(SUM(email_send_performed),0)+COALESCE(SUM(calendar_mutation_performed),0)
  FROM daily_brief_item_outcome_events
  UNION ALL SELECT 'ranking_policy_eval_runs',
    COALESCE(SUM(raw_email_body_persisted),0)+COALESCE(SUM(raw_document_text_persisted),0)+COALESCE(SUM(raw_calendar_payload_persisted),0)+COALESCE(SUM(raw_procore_payload_persisted),0)+COALESCE(SUM(raw_prompt_persisted),0)+COALESCE(SUM(raw_response_persisted),0)+COALESCE(SUM(signed_url_persisted),0)+COALESCE(SUM(download_url_persisted),0)+COALESCE(SUM(external_writeback_performed),0)+COALESCE(SUM(graph_writeback_performed),0)+COALESCE(SUM(procore_writeback_performed),0)+COALESCE(SUM(email_send_performed),0)+COALESCE(SUM(calendar_mutation_performed),0)
  FROM ranking_policy_eval_runs
  UNION ALL SELECT 'ranking_policy_eval_items',
    COALESCE(SUM(raw_email_body_persisted),0)+COALESCE(SUM(raw_document_text_persisted),0)+COALESCE(SUM(raw_calendar_payload_persisted),0)+COALESCE(SUM(raw_procore_payload_persisted),0)+COALESCE(SUM(raw_prompt_persisted),0)+COALESCE(SUM(raw_response_persisted),0)+COALESCE(SUM(signed_url_persisted),0)+COALESCE(SUM(download_url_persisted),0)+COALESCE(SUM(external_writeback_performed),0)+COALESCE(SUM(graph_writeback_performed),0)+COALESCE(SUM(procore_writeback_performed),0)+COALESCE(SUM(email_send_performed),0)+COALESCE(SUM(calendar_mutation_performed),0)
  FROM ranking_policy_eval_items
  UNION ALL SELECT 'model_profile_eval_results',
    COALESCE(SUM(raw_email_body_persisted),0)+COALESCE(SUM(raw_document_text_persisted),0)+COALESCE(SUM(raw_calendar_payload_persisted),0)+COALESCE(SUM(raw_procore_payload_persisted),0)+COALESCE(SUM(raw_prompt_persisted),0)+COALESCE(SUM(raw_response_persisted),0)+COALESCE(SUM(signed_url_persisted),0)+COALESCE(SUM(download_url_persisted),0)+COALESCE(SUM(external_writeback_performed),0)+COALESCE(SUM(graph_writeback_performed),0)+COALESCE(SUM(procore_writeback_performed),0)+COALESCE(SUM(email_send_performed),0)+COALESCE(SUM(calendar_mutation_performed),0)
  FROM model_profile_eval_results
  UNION ALL SELECT 'brief_effectiveness_rollups',
    COALESCE(SUM(raw_email_body_persisted),0)+COALESCE(SUM(raw_document_text_persisted),0)+COALESCE(SUM(raw_calendar_payload_persisted),0)+COALESCE(SUM(raw_procore_payload_persisted),0)+COALESCE(SUM(raw_prompt_persisted),0)+COALESCE(SUM(raw_response_persisted),0)+COALESCE(SUM(signed_url_persisted),0)+COALESCE(SUM(download_url_persisted),0)+COALESCE(SUM(external_writeback_performed),0)+COALESCE(SUM(graph_writeback_performed),0)+COALESCE(SUM(procore_writeback_performed),0)+COALESCE(SUM(email_send_performed),0)+COALESCE(SUM(calendar_mutation_performed),0)
  FROM brief_effectiveness_rollups
)
SELECT 'guard_zero_' || table_name AS check_name, guard_sum AS value FROM guard_sums;

SELECT 'eval_item_source_ref_coverage' AS check_name,
  CASE WHEN COUNT(*) = 0 THEN 1.0 ELSE ROUND(SUM(CASE WHEN source_ref_count > 0 THEN 1 ELSE 0 END) * 1.0 / COUNT(*), 4) END AS value,
  COUNT(*) AS eval_item_count
FROM ranking_policy_eval_items;

SELECT 'outcomes_without_candidate_row' AS check_name, COUNT(*) AS value
FROM daily_brief_item_outcome_events o
LEFT JOIN daily_brief_action_candidates c
  ON c.daily_brief_action_candidate_id = o.daily_brief_action_candidate_id
WHERE c.daily_brief_action_candidate_id IS NULL;

SELECT 'eval_items_without_eval_run' AS check_name, COUNT(*) AS value
FROM ranking_policy_eval_items i
LEFT JOIN ranking_policy_eval_runs r ON r.eval_run_id = i.eval_run_id
WHERE r.eval_run_id IS NULL;

WITH text_values AS (
  SELECT event_type AS value FROM daily_brief_exposure_events
  UNION ALL SELECT exposure_surface FROM daily_brief_exposure_events
  UNION ALL SELECT outcome_type FROM daily_brief_item_outcome_events
  UNION ALL SELECT policy_version FROM ranking_policy_eval_runs
  UNION ALL SELECT eval_mode FROM ranking_policy_eval_runs
  UNION ALL SELECT eval_notes_json FROM ranking_policy_eval_items
  UNION ALL SELECT scope_key FROM brief_effectiveness_rollups
)
SELECT 'sql_visible_url_or_email_or_token_hits' AS check_name, COUNT(*) AS value
FROM text_values
WHERE value LIKE '%http://%'
   OR value LIKE '%https://%'
   OR value LIKE '%@%.%'
   OR lower(value) LIKE '%bearer %'
   OR lower(value) LIKE '%access_token%'
   OR lower(value) LIKE '%refresh_token%'
   OR lower(value) LIKE '%private key%';
