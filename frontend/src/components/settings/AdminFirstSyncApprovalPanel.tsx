/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState } from 'react';
import {
  getAdminPendingApprovals,
  approveFirstSyncAdmin,
  rejectFirstSyncAdmin,
} from '../../lib/api';
import { ErrorState } from '../ui/ErrorState';

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
        setActionMsg('Approved. Updates are still controlled by the normal schedule.');
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
        setActionMsg('Rejected. The selection remains saved but will not update.');
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
      <h3 className="font-medium mb-2">Update Approval</h3>
      <div className="text-xs mb-2">
        Approve or reject saved project selections before new data appears.
      </div>

      <button className="badge" onClick={load} disabled={loading}>
        {loading ? 'Checking...' : 'Request update approval'}
      </button>

      <ErrorState message={error} onRetry={load} />

      {actionMsg && <div className="text-xs mt-2 text-green-600">{actionMsg}</div>}

      {items.length === 0 && !loading && (
        <div className="text-xs text-[var(--hb-muted)] mt-2">No update approvals are waiting.</div>
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
                    {busyId === cid ? 'Approving...' : 'Approve update'}
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
        Approval changes do not start updates.
      </div>
    </div>
  );
}
