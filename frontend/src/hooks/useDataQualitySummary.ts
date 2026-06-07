import { useQuery } from '@tanstack/react-query';
import {
  getDataQualitySummary,
  type DataQualitySummary,
} from '../lib/api';

/**
 * Prompt G — thin react-query wrapper for the sidebar-safe data quality indicator
 * (and embedded readiness data_quality). Also provides a plain async fetcher.
 * Mirrors the established useOnboardingReadiness pattern.
 */
export function useDataQualitySummary() {
  return useQuery<DataQualitySummary>({
    queryKey: ['settings', 'data-quality', 'summary'],
    queryFn: getDataQualitySummary,
    // Cheap advisory signal; stale-while-revalidate is appropriate.
    staleTime: 20_000,
  });
}

/** Non-hook fetch for one-off contexts (mirrors fetchOnboardingReadiness). */
export async function fetchDataQualitySummary(): Promise<DataQualitySummary> {
  return getDataQualitySummary();
}
