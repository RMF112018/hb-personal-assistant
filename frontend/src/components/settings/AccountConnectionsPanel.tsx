import { useConnectionsAccounts } from '../../hooks/useOnboardingReadiness';
import { GraphConnectionCard } from './GraphConnectionCard';
import { ProcoreConnectionCard } from './ProcoreConnectionCard';

export function AccountConnectionsPanel({ variant = 'settings' }: { variant?: 'get-started' | 'settings' }) {
  const { data: accounts, refetch, isFetching } = useConnectionsAccounts();

  const isGetStarted = variant === 'get-started';

  function handleCardComplete() {
    refetch();
  }

  return (
    <div className="card">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
        <h3 className="font-medium">{isGetStarted ? 'Account connections' : 'Account Connections'}</h3>
        <button className="badge" onClick={() => refetch()} disabled={isFetching}>
          {isFetching ? 'Checking...' : 'Check connection status'}
        </button>
      </div>

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
        Status checks do not start updates.
      </div>
    </div>
  );
}
