-- Email/calendar raw structured projection completeness smoke checks.
-- Run against a /tmp DB copy unless deliberately applying after merge.

.headers on
.mode column

SELECT 'email_message_raw_content' AS table_name, COUNT(*) AS rows,
       SUM(body_text IS NOT NULL AND TRIM(body_text) <> '') AS body_text_rows,
       SUM(body_html IS NOT NULL AND TRIM(body_html) <> '') AS body_html_rows
FROM email_message_raw_content
UNION ALL
SELECT 'calendar_event_raw_content' AS table_name, COUNT(*) AS rows,
       SUM(body_text IS NOT NULL AND TRIM(body_text) <> '') AS body_text_rows,
       SUM(body_html IS NOT NULL AND TRIM(body_html) <> '') AS body_html_rows
FROM calendar_event_raw_content;

-- Replace/add table names if implementation chooses different final structured projection names.
SELECT 'email_raw_message_structured' AS table_name,
       COUNT(*) AS rows,
       SUM(raw_email_id IS NOT NULL AND TRIM(raw_email_id) <> '') AS raw_linked_rows,
       SUM(source_quality IN ('graph_full_body','graph_body_preview_only','redacted_legacy_projection','metadata_only')) AS source_quality_classified_rows
FROM email_raw_message_structured;

SELECT 'email_raw_message_recipients_structured' AS table_name,
       COUNT(*) AS rows,
       SUM(message_projection_id IS NOT NULL AND TRIM(message_projection_id) <> '') AS parent_linked_rows,
       COUNT(DISTINCT message_projection_id) AS distinct_parent_rows
FROM email_raw_message_recipients_structured;

SELECT 'calendar_raw_event_structured' AS table_name,
       COUNT(*) AS rows,
       SUM(raw_calendar_event_id IS NOT NULL AND TRIM(raw_calendar_event_id) <> '') AS raw_linked_rows,
       SUM(source_quality IN ('graph_full_event_body','graph_body_preview_only','redacted_legacy_projection','metadata_only')) AS source_quality_classified_rows
FROM calendar_raw_event_structured;

SELECT 'calendar_raw_event_attendees_structured' AS table_name,
       COUNT(*) AS rows,
       SUM(event_projection_id IS NOT NULL AND TRIM(event_projection_id) <> '') AS parent_linked_rows,
       COUNT(DISTINCT event_projection_id) AS distinct_parent_rows
FROM calendar_raw_event_attendees_structured;
