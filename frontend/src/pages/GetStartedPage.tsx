/* eslint-disable @typescript-eslint/no-explicit-any */
import { Link } from 'react-router-dom';
import { useOnboardingReadiness } from '../hooks/useOnboardingReadiness';
import { ErrorState } from '../components/ui/ErrorState';
import { LoadingState } from '../components/ui/LoadingState';
import { AccountConnectionsPanel } from '../components/settings/AccountConnectionsPanel';

/**
 * Prompt D — Get Started page.
 * - First-time sessions are routed here by StartupRedirect (see routes.tsx).
 * - Explains the safe local-first sequence: connect (this page) → preview/save projects (Prompt E) → admin approval (Prompt F).
 * - "Connecting does not start sync" is repeated for clarity.
 * - Reuses the AccountConnectionsPanel for the Graph + Procore cards (interactive, safe, no raw secrets).
 * - For returning users who hit reauth_required but have prior setup, the panel + readiness will surface refresh/reauth affordances
 *   without forcing a full "first time" reset experience.
 */
export function GetStartedPage() {
  const { data, isLoading, error, refetch } = useOnboardingReadiness();

  if (isLoading) {
    return (
      <div className="max-w-2xl">
        <LoadingState label="Checking your local setup..." />
      </div>
    );
  }

  const state = data?.onboarding_state;
  const isFirstTime = state === 'first_time';
  const canGoToApp = !!data?.main_app_allowed || (state === 'ready' || state === 'degraded');

  return (
    <div className="max-w-2xl space-y-4 text-sm">
      <div className="card">
        <div className="font-medium mb-2">Welcome — connect your accounts locally</div>
        <div className="text-xs mb-3">
          This app pulls Microsoft 365 (Graph) and Procore data into your local environment and writes source-linked notes
          into your Obsidian vault. <strong>Everything stays on your machine.</strong>
        </div>
        <div className="advisory mb-2">
          Connecting does not start sync. You will preview projects, save selections, and an admin will approve the first sync
          before any data flows.
        </div>

        <div className="text-xs">
          Sequence:
          <ol className="list-decimal ml-5 mt-1 space-y-0.5">
            <li>Connect Microsoft 365 (this page)</li>
            <li>Connect Procore (this page)</li>
            <li>Project connections — choose what to follow (Prompt E)</li>
            <li>Admin reviews and approves first sync (Prompt F)</li>
          </ol>
        </div>

        {!isFirstTime && (
          <div className="text-[10px] text-[var(--hb-muted)] mt-2">
            Returning user detected. If auth is stale you will see refresh / re-auth options below. Your prior setup and data
            are preserved.
          </div>
        )}
      </div>

      <ErrorState message={error ? (error as any)?.message || String(error) : null} onRetry={() => refetch()} />

      {/* The interactive, safe connection cards live here (and are reused on Settings). */}
      <AccountConnectionsPanel variant="get-started" />

      <div className="flex flex-wrap gap-2">
        {canGoToApp ? (
          <Link to="/today" className="badge">
            Continue to Today
          </Link>
        ) : (
          <div className="text-xs text-[var(--hb-muted)]">Complete at least one account connection above to enable the main app.</div>
        )}
        <Link to="/settings" className="badge">Open full Settings</Link>
      </div>

      <div className="advisory">
        All account operations use the normalized backend contract. No tokens, secrets, or cache paths are ever shown to the UI.
        Local role selector (viewer / operator / admin) in the header is for dev simulation only.
      </div>
    </div>
  );
}
