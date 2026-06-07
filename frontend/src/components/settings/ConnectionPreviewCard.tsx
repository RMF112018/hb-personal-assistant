/* eslint-disable @typescript-eslint/no-explicit-any */
import { ErrorState } from '../ui/ErrorState';

/**
 * Prompt E — Connection Preview Card.
 * Renders a sanitized preview result from /api/settings/connections/projects/preview.
 * - Shows detected type, proposed safe metadata (ids, urls, names, policies).
 * - Explicitly states "Preview complete. No sync has started." and admin approval requirement.
 * - Warnings are advisory only (e.g. large OneDrive scope).
 * - Provides a "Save connection" action when ready (wired by parent panel).
 * Never renders raw external payloads, tokens, or secrets.
 */
export function ConnectionPreviewCard({
  preview,
  onSave,
  saving = false,
  saveError,
}: {
  preview: any;
  onSave?: () => void | Promise<void>;
  saving?: boolean;
  saveError?: string | null;
}) {
  if (!preview) return null;

  const status = preview.status || preview.first_sync_status || 'unknown';
  const ready = status === 'ready_to_save' || preview.status === 'ready_to_save';
  const detected = preview.detected_source_type || preview.source_type || 'unknown';
  const proposed = preview.proposed_source || preview.parsed || {};
  const warnings: string[] = preview.warnings || [];
  const firstSync = preview.first_sync_status || 'pending_admin_approval';
  const adminReq = preview.admin_approval_required !== false;

  function safeText(v: any): string {
    if (v == null) return '';
    if (typeof v === 'string') return v;
    try { return JSON.stringify(v); } catch { return String(v); }
  }

  return (
    <div className="card mt-3">
      <div className="font-medium mb-1 flex items-center gap-2">
        Preview result
        <span className={`badge ${ready ? 'badge-fresh' : 'badge-stale'}`}>{status}</span>
        <span className="badge badge-muted">{detected}</span>
      </div>

      {preview.message && <div className="text-xs mb-1">{preview.message}</div>}

      <div className="text-xs mb-2">
        <div><strong>Preview complete. No sync has started.</strong></div>
        {adminReq && <div>First sync requires admin approval (pending_admin_approval).</div>}
        {firstSync && <div>first_sync_status: {firstSync}</div>}
      </div>

      {Object.keys(proposed).length > 0 && (
        <div className="text-xs mb-2">
          <div className="font-medium mb-0.5">Proposed source (safe metadata)</div>
          <div className="bg-[var(--hb-bg)] border border-[var(--hb-border)] rounded p-2 font-mono text-[10px] whitespace-pre-wrap">
            {Object.entries(proposed).map(([k, v]) => `${k}: ${safeText(v)}`).join('\n')}
          </div>
        </div>
      )}

      {warnings.length > 0 && (
        <div className="text-xs mb-2">
          <div className="font-medium mb-0.5">Warnings</div>
          <ul className="list-disc ml-4">
            {warnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      )}

      <ErrorState message={saveError || null} />

      {ready && onSave && (
        <button
          className="badge"
          onClick={onSave}
          disabled={saving}
        >
          {saving ? 'Saving…' : 'Save connection'}
        </button>
      )}

      <div className="advisory mt-2">
        Preview is local metadata only. Save persists configuration and queues for admin first-sync approval. No external data is fetched or written during preview/save.
      </div>
    </div>
  );
}
