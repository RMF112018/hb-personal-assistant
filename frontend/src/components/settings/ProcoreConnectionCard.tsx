/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useRef, useState } from 'react';
import {
  startProcoreAuth,
  getProcoreAuthStatus,
  exchangeProcoreCode,
  disconnectProcoreLocal,
  type ProcoreAuthStartResult,
  type AuthFlowStatus,
} from '../../lib/api';
import { ErrorState } from '../ui/ErrorState';

/**
 * Prompt D — Procore connection card.
 * - Drives the normalized OAuth start + (callback or manual code) flow.
 * - Start returns a safe authorization_url. Primary UX: "Open Procore to authorize" (opens the URL).
 * - Backend callback (or manual exchange) completes the server-side token handling.
 * - This card polls status; on terminal success the parent refreshes accounts/readiness for verified state.
 * - Manual code fallback is shown when the start response indicates it is available (oob or when registered redirect requires it).
 * - Disconnect is local-cache only.
 * - Never renders tokens, codes (beyond the one the user pastes for manual), state values, cache paths, or raw Procore payloads.
 */
export function ProcoreConnectionCard({
  procoreStatus,
  onComplete,
  compact = false,
}: {
  procoreStatus?: any;
  onComplete?: () => void;
  compact?: boolean;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [startResult, setStartResult] = useState<ProcoreAuthStartResult | null>(null);
  const [pollStatus, setPollStatus] = useState<AuthFlowStatus | null>(null);
  const [manualCode, setManualCode] = useState('');
  const [error, setError] = useState<string | null>(null);
  const pollTimer = useRef<number | null>(null);
  const mounted = useRef(true);

  const currentAuthStatus: string = procoreStatus?.status || (procoreStatus?.access_cached ? 'connected_valid' : 'never_connected');
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
      const res = await startProcoreAuth();
      setStartResult(res);
      const flowId = res.flow_id;
      // Start polling immediately; user will complete in the opened window (callback) or paste code for manual.
      pollTimer.current = window.setInterval(async () => {
        try {
          const s = await getProcoreAuthStatus(flowId);
          if (!mounted.current) return;
          setPollStatus(s);
          if (s.status === 'complete' || s.status === 'expired' || s.status === 'failed') {
            clearPoll();
            if (s.status === 'complete') {
              onComplete?.();
            }
          }
        } catch {
          // continue polling
        }
      }, 4000);
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setBusy(null);
    }
  }

  function openAuthUrl() {
    if (startResult?.authorization_url) {
      window.open(startResult.authorization_url, '_blank', 'noopener');
    }
  }

  async function handleManualExchange() {
    if (!manualCode.trim()) return;
    setBusy('exchange');
    setError(null);
    try {
      await exchangeProcoreCode({ code: manualCode.trim() });
      // After exchange the flow should resolve; give the poll a moment or force a status check if we have flow.
      // For simplicity, clear local flow UI and let parent refetch; if poll is running it will pick up complete.
      setManualCode('');
      onComplete?.();
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
      await disconnectProcoreLocal();
      setStartResult(null);
      setPollStatus(null);
      clearPoll();
      onComplete?.();
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setBusy(null);
    }
  }

  const showFlow = !!startResult && (!pollStatus || pollStatus.status === 'pending');
  const showManual = !!startResult && (startResult.manual_code_fallback_available || startResult.callback_mode === 'oob');

  return (
    <div className={compact ? 'text-xs' : ''}>
      <div className="font-medium mb-1 flex items-center gap-2">
        Procore
        <span className="badge">{currentAuthStatus.replace(/_/g, ' ')}</span>
      </div>

      {isConnected ? (
        <div className="text-xs mb-2">
          Connected.
          <button className="badge ml-2" onClick={handleDisconnect} disabled={!!busy}>
            {busy === 'disconnect' ? 'Disconnecting…' : 'Disconnect (local only)'}
          </button>
        </div>
      ) : (
        <button className="badge" onClick={handleStart} disabled={!!busy || !!showFlow}>
          {busy === 'start' ? 'Starting…' : 'Connect Procore'}
        </button>
      )}

      <ErrorState message={error} onRetry={handleStart} />

      {showFlow && startResult && (
        <div className="mt-2 card text-xs">
          <div className="font-medium mb-1">Authorize in Procore</div>
          <button className="badge" onClick={openAuthUrl}>
            Open Procore to authorize
          </button>
          <div className="text-[10px] text-[var(--hb-muted)] mt-2">
            A new tab/window will open. Complete authorization there. This page will update automatically when the callback finishes.
            Connecting does not start sync.
          </div>

          {showManual && (
            <div className="mt-3 border-t border-[var(--hb-border)] pt-2">
              <div className="text-[10px] mb-1">Manual code fallback (if the browser flow cannot complete):</div>
              <div className="flex gap-2">
                <input
                  className="border bg-[var(--hb-bg)] px-2 py-1 text-xs flex-1"
                  placeholder="Paste authorization code"
                  value={manualCode}
                  onChange={(e) => setManualCode(e.target.value)}
                  aria-label="Procore authorization code for manual exchange"
                />
                <button className="badge" onClick={handleManualExchange} disabled={!!busy || !manualCode.trim()}>
                  {busy === 'exchange' ? 'Exchanging…' : 'Exchange code'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {pollStatus && (
        <div className="mt-1 text-xs">
          {pollStatus.status === 'pending' && 'Waiting for Procore authorization to complete…'}
          {pollStatus.status === 'complete' && 'Procore connected.'}
          {pollStatus.status === 'expired' && 'Authorization window expired. Start again.'}
          {pollStatus.status === 'failed' && 'Authorization failed. You can try again.'}
        </div>
      )}

      <div className="text-[10px] text-[var(--hb-muted)] mt-1">
        Backend-controlled OAuth. Callback or manual exchange happens server-side. No tokens or secrets shown here.
      </div>
    </div>
  );
}
