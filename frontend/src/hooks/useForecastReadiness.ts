import { useQuery } from '@tanstack/react-query'

import { getForecastRuntimeStatus } from '../lib/api'

/* Thin react-query wrapper over the redaction-safe forecast runtime status. Drives the onboarding
 * readiness panel (mirrors useOnboardingReadiness). Status is cheap + advisory. */
export function useForecastReadiness() {
  return useQuery({
    queryKey: ['forecast', 'runtime', 'status'],
    queryFn: () => getForecastRuntimeStatus(),
    staleTime: 15_000,
  })
}
