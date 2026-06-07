import { useConnectionsAccounts } from '../../hooks/useOnboardingReadiness';
import { GraphConnectionCard } from './GraphConnectionCard';
import { ProcoreConnectionCard } from './ProcoreConnectionCard';

/**
 * Prompt D — reusable Account Connections surface.
 * - Composes the Graph and Procore interactive cards.
 * - variant="get-started" | "settings" tweaks heading density and explanatory copy.
 * - On card terminal success, refetches the accounts summary so badges and parent readiness update.
 * - All data flowing here is safe (no tokens, secrets, paths, raw payloads).
 */
export function AccountConnectionsPanel({ variant = 'settings' }: { variant?: 'get-started' | 'settings' }) {
  const { data: accounts, refetch } = useConnectionsAccounts();

  const isGetStarted = variant === 'get-started';

  function handleCardComplete() {
    // Refresh so the cards re-render with updated connected state from the safe accounts summary.
    refetch();
  }

  return (
    <div className="card">
      <div className="font-medium mb-2">{isGetStarted ? 'Account connections' : 'Account Connections (Prompt 14B / D)'}</div>

      {isGetStarted && (
        <div className="text-xs mb-3 text-[var(--hb-muted)]">
          Connect Microsoft 365 and/or Procore below. You can always adjust later in Settings.
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <div className="border border-[var(--hb-border)] rounded p-3">
          <GraphConnectionCard
            graphStatus={accounts?.graph}
            onComplete={handleCardComplete}
            compact={!isGetStarted}
          />
        </div>
        <div className="border border-[var(--hb-border)] rounded p-3">
          <ProcoreConnectionCard
            procoreStatus={accounts?.procore}
            onComplete={handleCardComplete}
            compact={!isGetStarted}
          />
        </div>
      </div>

      <div className="text-[10px] text-[var(--hb-muted)] mt-2">
        Status is advisory. Connecting never starts sync. Use the header role selector for local dev simulation of viewer/operator/admin.
      </div>
    </div>
  );
}
