/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState } from 'react';
import {
  getAdminPendingApprovals,
  approveFirstSyncAdmin,
  rejectFirstSyncAdmin,
} from '../../lib/api';
import { ErrorState } from '../ui/ErrorState';

/**
 * Prompt F — Admin First-Sync Approval Panel.
 * - Loads pending first-sync approvals via admin-only surface (getSettingsAdminSync equivalent).
 * - Renders safe list (connection/project ids, status, timestamps).
 * - Approve and Reject actions (POST to normalized admin endpoints) — backend requires admin role (403 otherwise).
 * - After action, refetches list. Explicit notes that these actions do not start sync (first_sync_triggered=false).
 * - Placed in Settings admin section; non-admins see 403 on mutate (or can be hidden by role in future).
 */
export function AdminFirstSyncApprovalPanel() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    setActionMsg(null);
    try {
      const res = await getAdminPendingApprovals();
      const list = (res && (res.items || res.pending_approvals?.items)) || [];
      setItems(Array.isArray(list) ? list : []);
    } catch (e: any) {
      setError(e?.message || String(e));
      setItems([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, []);

  async function doApprove(id: string) {
    setBusyId(id);
    setActionMsg(null);
    setError(null);
    try {
      const r = await approveFirstSyncAdmin(id);
      if (r && r.ok === false) {
        setActionMsg(`Approve failed: ${r.reason_code || r.kind || 'unknown'}`);
      } else {
        setActionMsg('Approved. First sync not started (pending scheduling).');
      }
      await load();
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setBusyId(null);
    }
  }

  async function doReject(id: string) {
    setBusyId(id);
    setActionMsg(null);
    setError(null);
    try {
      const r = await rejectFirstSyncAdmin(id);
      if (r && r.ok === false) {
        setActionMsg(`Reject failed: ${r.reason_code || r.kind || 'unknown'}`);
      } else {
        setActionMsg('Rejected. Connection remains locally configured but will not sync.');
      }
      await load();
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="card">
      <div className="font-medium mb-2">First-sync approvals (admin only)</div>
      <div className="text-xs mb-2">
        Approve or reject pending first-sync for saved connections (Procore projects and Microsoft sources).
        Approvals do not start sync. Only admins can act; non-admin calls are rejected by the backend.
      </div>

      <button className="badge" onClick={load} disabled={loading}>
        {loading ? 'Refreshing…' : 'Refresh pending list'}
      </button>

      <ErrorState message={error} onRetry={load} />

      {actionMsg && <div className="text-xs mt-2 text-green-600">{actionMsg}</div>}

      {items.length === 0 && !loading && (
        <div className="text-xs text-[var(--hb-muted)] mt-2">No pending first-sync approvals.</div>
      )}

      {items.length > 0 && (
        <div className="mt-2 space-y-2 text-xs">
          {items.map((it: any, idx: number) => {
            const cid = it.connection_like_id || it.source_id || it.connection_id || it.id || `item-${idx}`;
            const status = it.sync_status || it.project_stage || it.status || 'pending';
            return (
              <div key={idx} className="border border-[var(--hb-border)] rounded p-2">
                <div className="flex items-center gap-2">
                  <span className="font-mono break-all">{cid}</span>
                  <span className="badge">{status}</span>
                  {it.project_key && <span className="badge badge-muted">{it.project_key}</span>}
                </div>
                {it.source_name && <div>source: {it.source_name}</div>}
                {it.last_attempted && <div className="text-[10px] text-[var(--hb-muted)]">last: {it.last_attempted}</div>}
                <div className="mt-1 flex gap-2">
                  <button
                    className="badge"
                    onClick={() => doApprove(cid)}
                    disabled={!!busyId}
                  >
                    {busyId === cid ? 'Approving…' : 'Approve first sync'}
                  </button>
                  <button
                    className="badge"
                    onClick={() => doReject(cid)}
                    disabled={!!busyId}
                  >
                    {busyId === cid ? 'Rejecting…' : 'Reject'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="advisory mt-3">
        These actions update local approval state only. No live sync is triggered (first_sync_triggered remains false).
        Scheduled or manual sync paths consult the same status before proceeding.
      </div>
    </div>
  );
}
