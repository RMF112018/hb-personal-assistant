-- Raw-free validation helpers.
-- Adjust table/column names to repo truth before use.

-- New ranking guard columns must remain zero.
SELECT 'daily_brief_ranking_runs' AS table_name, COUNT(*) AS bad_rows
FROM daily_brief_ranking_runs
WHERE
  COALESCE(raw_content_guard, 0) != 0
  OR COALESCE(external_writeback_guard, 0) != 0;

-- Surfaceable ranked candidates must retain source refs.
SELECT COUNT(*) AS ranked_without_source_refs
FROM daily_brief_ranked_candidates
WHERE COALESCE(source_ref_count, 0) <= 0;

-- Model must not mark deterministic fallback as clean model success.
SELECT COUNT(*) AS fallback_status_contradictions
FROM daily_brief_ranking_runs
WHERE deterministic_fallback_used = 1
  AND model_status = 'ok'
  AND degraded_reason IS NULL;
