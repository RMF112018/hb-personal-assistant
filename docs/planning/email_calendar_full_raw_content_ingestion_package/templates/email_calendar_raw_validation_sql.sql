-- Email + Calendar Raw Content Validation SQL
-- Run only against a /tmp copy of the SQLite DB.
-- Do not paste query results containing raw body columns into repo evidence.

-- 1) Schema head
SELECT MAX(version) AS schema_head FROM schema_migrations;

-- 2) Table existence
SELECT name
FROM sqlite_master
WHERE type = 'table'
  AND name IN (
    'raw_content_policy_state',
    'email_message_raw_content',
    'email_thread_raw_context',
    'calendar_event_raw_content',
    'raw_content_model_context_packets',
    'raw_content_access_events',
    'emails',
    'email_messages',
    'calendar_events',
    'calendar_event_index'
  )
ORDER BY name;

-- 3) Raw policy state counts only
SELECT COUNT(*) AS raw_content_policy_state_rows FROM raw_content_policy_state;

-- 4) Email raw coverage counts only
SELECT
  COUNT(*) AS rows,
  SUM(CASE WHEN body_preview IS NOT NULL AND length(body_preview) > 0 THEN 1 ELSE 0 END) AS body_preview_non_null,
  SUM(CASE WHEN body_text IS NOT NULL AND length(body_text) > 0 THEN 1 ELSE 0 END) AS body_text_non_null,
  SUM(CASE WHEN body_html IS NOT NULL AND length(body_html) > 0 THEN 1 ELSE 0 END) AS body_html_non_null
FROM email_message_raw_content;

-- 5) Email source-quality distribution, if source_quality exists.
-- If this errors, migration has not added the column yet.
SELECT source_quality, COUNT(*) AS rows
FROM email_message_raw_content
GROUP BY source_quality
ORDER BY rows DESC, source_quality;

-- 6) Thread raw context coverage counts only
SELECT
  COUNT(*) AS rows,
  SUM(CASE WHEN messages_json IS NOT NULL AND length(messages_json) > 2 THEN 1 ELSE 0 END) AS messages_json_non_empty,
  SUM(CASE WHEN message_count > 0 THEN 1 ELSE 0 END) AS message_count_non_zero,
  SUM(CASE WHEN model_ready = 1 THEN 1 ELSE 0 END) AS model_ready_rows
FROM email_thread_raw_context;

-- 7) Calendar raw coverage counts only
SELECT
  COUNT(*) AS rows,
  SUM(CASE WHEN body_preview IS NOT NULL AND length(body_preview) > 0 THEN 1 ELSE 0 END) AS body_preview_non_null,
  SUM(CASE WHEN body_text IS NOT NULL AND length(body_text) > 0 THEN 1 ELSE 0 END) AS body_text_non_null,
  SUM(CASE WHEN body_html IS NOT NULL AND length(body_html) > 0 THEN 1 ELSE 0 END) AS body_html_non_null,
  SUM(CASE WHEN attendees_json IS NOT NULL AND length(attendees_json) > 2 THEN 1 ELSE 0 END) AS attendees_non_empty,
  SUM(CASE WHEN location_display IS NOT NULL AND length(location_display) > 0 THEN 1 ELSE 0 END) AS location_non_null,
  SUM(CASE WHEN join_url IS NOT NULL AND length(join_url) > 0 THEN 1 ELSE 0 END) AS join_url_non_null
FROM calendar_event_raw_content;

-- 8) Calendar source-quality distribution, if source_quality exists.
SELECT source_quality, COUNT(*) AS rows
FROM calendar_event_raw_content
GROUP BY source_quality
ORDER BY rows DESC, source_quality;

-- 9) Access audit counts only
SELECT source_family, access_purpose, raw_included, COUNT(*) AS rows
FROM raw_content_access_events
GROUP BY source_family, access_purpose, raw_included
ORDER BY source_family, access_purpose, raw_included;

-- 10) Model context packets counts only
SELECT source_family, raw_included, COUNT(*) AS rows
FROM raw_content_model_context_packets
GROUP BY source_family, raw_included
ORDER BY source_family, raw_included;
