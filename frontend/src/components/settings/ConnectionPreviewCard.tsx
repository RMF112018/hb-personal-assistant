/* eslint-disable @typescript-eslint/no-explicit-any */
import { ErrorState } from '../ui/ErrorState';
import { TechnicalDetails } from '../common/TechnicalDetails';
import { safeDisplayText } from '../../lib/errorCopy';

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
  const title = proposed.source_name || proposed.project_name || proposed.project_key || preview.message || 'Project selection'

  return (
    <div className="card mt-3">
      <div className="font-medium mb-1 flex items-center gap-2">
        Review result
        <span className={`badge ${ready ? 'badge-fresh' : 'badge-stale'}`}>{ready ? 'Ready to save' : 'Needs review'}</span>
        <span className="badge badge-muted">{labelSource(detected)}</span>
      </div>

      <div className="text-xs mb-1">{safeDisplayText(title, 'Project selection ready for review.')}</div>

      <div className="text-xs mb-2">
        <div><strong>Review complete. No updates have started.</strong></div>
        {adminReq && <div>Request update approval before new data appears.</div>}
        {firstSync && <div>{labelStatus(firstSync)}</div>}
      </div>

      {Object.keys(proposed).length > 0 && (
        <TechnicalDetails
          summary="Advanced details"
          details={Object.entries(proposed).map(([key, value]) => `${key}: ${safeDisplayText(value)}`).join('\n')}
          className="mb-2 text-xs"
        />
      )}

      {warnings.length > 0 && (
        <TechnicalDetails
          summary="Warnings"
          details={warnings.join('\n')}
          className="mb-2 text-xs"
        />
      )}

      <ErrorState message={saveError || null} />

      {ready && onSave && (
        <button
          className="badge"
          onClick={onSave}
          disabled={saving}
        >
          {saving ? 'Saving...' : 'Save project selections'}
        </button>
      )}

      <div className="advisory mt-2">
        Reviewing and saving project selections does not start updates.
      </div>
    </div>
  );
}

function labelSource(value: unknown) {
  const text = String(value || 'source').replace(/_/g, ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

function labelStatus(value: unknown) {
  const status = String(value || '')
  if (status.includes('pending')) return 'Waiting for update approval.'
  if (status.includes('approved')) return 'Approved for updates.'
  if (status.includes('rejected')) return 'Needs review.'
  return ''
}
