/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useRef, useState } from 'react';
import {
  startGraphDeviceAuth,
  getGraphAuthStatus,
  disconnectGraphLocal,
  type GraphAuthStartResult,
  type AuthFlowStatus,
} from '../../lib/api';
import { ErrorState } from '../ui/ErrorState';

export function GraphConnectionCard({
  graphStatus,
  onComplete,
  compact = false,
}: {
  graphStatus?: any; // safe slice from /accounts or readiness (status, account hints, etc.)
  onComplete?: () => void;
  compact?: boolean;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [startResult, setStartResult] = useState<GraphAuthStartResult | null>(null);
  const [pollStatus, setPollStatus] = useState<AuthFlowStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollTimer = useRef<number | null>(null);
  const mounted = useRef(true);

  const currentAuthStatus: string = graphStatus?.status || (graphStatus?.connected ? 'connected_valid' : 'never_connected');
  const isConnected = currentAuthStatus === 'connected_valid' || currentAuthStatus === 'connected_refreshing';

  function clearPoll() {
    if (pollTimer.current) {
      window.clearInterval(pollTimer.current);
      pollTimer.current = null;
    }
  }

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      clearPoll();
    };
  }, []);

  async function handleStart() {
    setBusy('start');
    setError(null);
    setStartResult(null);
    setPollStatus(null);
    clearPoll();
    try {
      const res = await startGraphDeviceAuth();
      setStartResult(res);
      // Begin polling
      const flowId = res.flow_id;
      pollTimer.current = window.setInterval(async () => {
        try {
          const s = await getGraphAuthStatus(flowId);
          if (!mounted.current) return;
          setPollStatus(s);
          if (s.status === 'complete' || s.status === 'expired' || s.status === 'failed') {
            clearPoll();
            if (s.status === 'complete') {
              onComplete?.();
            }
          }
        } catch {
          if (!mounted.current) return;
          // Non-fatal poll error; keep going until timeout or manual stop
        }
      }, 4000);
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setBusy(null);
    }
  }

  async function handleDisconnect() {
    setBusy('disconnect');
    setError(null);
    try {
      await disconnectGraphLocal();
      // Clear any in-flight UI state
      setStartResult(null);
      setPollStatus(null);
      clearPoll();
      onComplete?.(); // parent will refetch accounts/readiness
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setBusy(null);
    }
  }

  function copy(text: string) {
    try {
      navigator.clipboard.writeText(text);
    } catch {
      // ignore
    }
  }

  const showFlow = !!startResult && (!pollStatus || pollStatus.status === 'pending');

  return (
    <div className={compact ? 'text-xs' : ''}>
      <div className="font-medium mb-1 flex items-center gap-2">
        Microsoft 365
        <span className="badge">{currentAuthStatus.replace(/_/g, ' ')}</span>
      </div>

      {isConnected ? (
        <div className="text-xs mb-2">
          Connected{graphStatus?.account_hint ? ` • ${graphStatus.account_hint}` : ''}.
          <button className="badge ml-2" onClick={handleDisconnect} disabled={!!busy}>
            {busy === 'disconnect' ? 'Disconnecting…' : 'Disconnect (local only)'}
          </button>
        </div>
      ) : (
        <button className="badge" onClick={handleStart} disabled={!!busy || !!showFlow}>
          {busy === 'start' ? 'Starting…' : 'Connect Microsoft 365'}
        </button>
      )}

      <ErrorState message={error} onRetry={handleStart} />

      {/* One-time device code + verification UI (safe to display per contract) */}
      {showFlow && startResult && (
        <div className="mt-2 card text-xs">
          <div className="font-medium mb-1">Complete sign-in in your browser</div>
          <div className="mb-1">
            Enter this code at the Microsoft sign-in page:
          </div>
          <div className="font-mono text-base tracking-[3px] bg-[var(--hb-bg)] border border-[var(--hb-border)] rounded px-3 py-2 select-all">
            {startResult.user_code}
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            <button className="badge" onClick={() => copy(startResult.user_code)}>Copy code</button>
            <a
              className="badge underline"
              href={startResult.verification_uri_complete || startResult.verification_uri}
              target="_blank"
              rel="noreferrer"
            >
              Open sign-in page
            </a>
          </div>
          <div className="text-[10px] text-[var(--hb-muted)] mt-2">
            The code expires soon. Keep this tab open while you complete the sign-in in the other window/tab.
            Connecting does not start sync.
          </div>
        </div>
      )}

      {/* Poll status feedback */}
      {pollStatus && (
        <div className="mt-1 text-xs">
          {pollStatus.status === 'pending' && 'Waiting for sign-in to complete…'}
          {pollStatus.status === 'complete' && 'Microsoft 365 connected.'}
          {pollStatus.status === 'expired' && 'Sign-in window expired. Start again.'}
          {pollStatus.status === 'failed' && 'Sign-in failed. You can try again.'}
        </div>
      )}

      <div className="text-[10px] text-[var(--hb-muted)] mt-1">
        Uses device code flow. No tokens or secrets are stored or shown in the UI.
      </div>
    </div>
  );
}
