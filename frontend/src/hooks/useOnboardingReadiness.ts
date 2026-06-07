import { useQuery } from '@tanstack/react-query';
import {
  getOnboardingReadiness,
  getSettingsAccounts,
  type OnboardingReadinessResponse,
  type ConnectionsAccountsResponse,
} from '../lib/api';

/**
 * Prompt D — thin react-query wrapper for startup readiness (first_time vs reauth_required etc.).
 * Also provides a plain async fetcher for route-level guards (StartupRedirect) that must not use hooks.
 */
export function useOnboardingReadiness() {
  return useQuery<OnboardingReadinessResponse>({
    queryKey: ['onboarding', 'readiness'],
    queryFn: getOnboardingReadiness,
    // Readiness is cheap and advisory; stale-while-revalidate is fine.
    staleTime: 15_000,
  });
}

/** Non-hook fetch for redirect gates and one-off checks (avoids hook rules outside components). */
export async function fetchOnboardingReadiness(): Promise<OnboardingReadinessResponse> {
  return getOnboardingReadiness();
}

/** Optional accounts summary hook for cards/panels that want live status. */
export function useConnectionsAccounts() {
  return useQuery<ConnectionsAccountsResponse>({
    queryKey: ['settings', 'connections', 'accounts'],
    queryFn: getSettingsAccounts,
    staleTime: 20_000,
  });
}

export async function fetchConnectionsAccounts(): Promise<ConnectionsAccountsResponse> {
  return getSettingsAccounts();
}
