-- Lifecycle validation SQL. Safe aggregate checks only.

SELECT name
FROM sqlite_master
WHERE type='table'
  AND name IN ('candidate_lifecycle_events','candidate_merge_links','candidate_suppression_rules','candidate_feedback_summary','candidate_review_queue')
ORDER BY name;

SELECT 'candidate_lifecycle_events' AS table_name,
       CASE WHEN EXISTS (SELECT 1 FROM sqlite_master WHERE type='table' AND name='candidate_lifecycle_events')
            THEN (SELECT COUNT(*) FROM candidate_lifecycle_events)
            ELSE NULL END AS row_count;

SELECT 'candidate_merge_links' AS table_name,
       CASE WHEN EXISTS (SELECT 1 FROM sqlite_master WHERE type='table' AND name='candidate_merge_links')
            THEN (SELECT COUNT(*) FROM candidate_merge_links)
            ELSE NULL END AS row_count;

SELECT 'candidate_suppression_rules' AS table_name,
       CASE WHEN EXISTS (SELECT 1 FROM sqlite_master WHERE type='table' AND name='candidate_suppression_rules')
            THEN (SELECT COUNT(*) FROM candidate_suppression_rules)
            ELSE NULL END AS row_count;

-- Guard checks should be expanded by implementation to include new lifecycle tables if added.

