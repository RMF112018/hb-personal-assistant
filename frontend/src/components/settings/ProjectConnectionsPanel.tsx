/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useConnectionsAccounts } from '../../hooks/useOnboardingReadiness';
import {
  previewProjectConnection,
  saveProjectConnection,
  getProjectConnections,
} from '../../lib/api';
import { ErrorState } from '../ui/ErrorState';
import { ConnectionPreviewCard } from './ConnectionPreviewCard';

/**
 * Prompt E — Project Connections auth-aware panel.
 * - Form supports Procore homepage URL, SharePoint site/folder/share-link, OneDrive (scope_mode + selected ids),
 *   and Outlook/Calendar include toggles (default false = project_matching_only semantics).
 * - Auth gating: Procore sources disabled unless procore account is connected_valid; Microsoft sources gated on graph.
 * - Preview (viewer ok) → renders ConnectionPreviewCard with explicit "no sync" and "admin approval" messaging.
 * - Save (operator) persists and refetches list; shows pending/approved/rejected status from backend.
 * - All via normalized /api/settings/connections/projects/* (safe metadata only).
 */
export function ProjectConnectionsPanel() {
  const { data: accounts } = useConnectionsAccounts();

  const graphStatus = accounts?.graph?.status || (accounts?.graph?.connected ? 'connected_valid' : 'never_connected');
  const procoreStatus = accounts?.procore?.status || (accounts?.procore?.access_cached ? 'connected_valid' : 'never_connected');

  const graphOk = graphStatus === 'connected_valid';
  const procoreOk = procoreStatus === 'connected_valid';

  const [url, setUrl] = useState('');
  const [projectKey, setProjectKey] = useState('');
  const [sourceName, setSourceName] = useState('');
  const [scopeMode, setScopeMode] = useState<string>('');
  const [selectedIds, setSelectedIds] = useState(''); // comma separated for simplicity
  const [includeOutlook, setIncludeOutlook] = useState(false);
  const [includeCalendar, setIncludeCalendar] = useState(false);

  const [preview, setPreview] = useState<any>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const [saveError, setSaveError] = useState<string | null>(null);

  const [list, setList] = useState<any>(null);
  const [listError, setListError] = useState<string | null>(null);

  async function refreshList() {
    setListError(null);
    try {
      const res = await getProjectConnections();
      setList(res);
    } catch (e: any) {
      setListError(e?.message || String(e));
    }
  }

  useEffect(() => {
    // Initial population of the saved connections list (setState inside effect is intentional for mount-once fetch; matches patterns elsewhere in the app).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshList();
  }, []);

  function resetPreview() {
    setPreview(null);
    setPreviewError(null);
    setSaveError(null);
  }

  async function doPreview() {
    setBusy('preview');
    setPreviewError(null);
    setSaveError(null);
    setPreview(null);
    try {
      const body: any = {};
      if (url) body.url = url;
      if (projectKey) body.project_key = projectKey;
      if (sourceName) body.source_name = sourceName;
      if (scopeMode) body.scope_mode = scopeMode;
      if (selectedIds.trim()) body.selected_folder_item_ids = selectedIds.split(',').map(s => s.trim()).filter(Boolean);
      if (includeOutlook) body.include_outlook = true;
      if (includeCalendar) body.include_calendar = true;

      const res = await previewProjectConnection(body);
      setPreview(res);
    } catch (e: any) {
      setPreviewError(e?.message || String(e));
    } finally {
      setBusy(null);
    }
  }

  async function doSave() {
    setBusy('save');
    setSaveError(null);
    try {
      // Rebuild body from current form (or from preview.proposed if desired; use form for fidelity)
      const body: any = {};
      if (url) body.url = url;
      if (projectKey) body.project_key = projectKey;
      if (sourceName) body.source_name = sourceName;
      if (scopeMode) body.scope_mode = scopeMode;
      if (selectedIds.trim()) body.selected_folder_item_ids = selectedIds.split(',').map(s => s.trim()).filter(Boolean);
      if (includeOutlook) body.include_outlook = true;
      if (includeCalendar) body.include_calendar = true;

      const res = await saveProjectConnection(body);
      if (!res?.ok) {
        setSaveError(res?.reason_code || 'Save failed');
      } else {
        setPreview(null);
        await refreshList();
        // Keep form for further entries; user can clear manually
      }
    } catch (e: any) {
      setSaveError(e?.message || String(e));
    } finally {
      setBusy(null);
    }
  }

  const pendingItems: any[] = (list?.pending_approvals?.items || list?.items || []);

  return (
    <div className="card">
      <div className="font-medium mb-2">Project Connections (Prompt E)</div>

      <div className="text-xs mb-3">
        Enter a project/source URL (or calendar options) then Preview. Preview and Save do not start sync.
        First live sync requires separate admin approval.
      </div>

      {/* Auth gating messages */}
      {!procoreOk && (
        <div className="text-xs mb-1 text-amber-600">
          Procore sources require a connected Procore account. <Link to="/settings" className="underline">Connect Procore</Link> or <Link to="/get-started" className="underline">Get Started</Link>.
        </div>
      )}
      {!graphOk && (
        <div className="text-xs mb-1 text-amber-600">
          Microsoft sources (SharePoint, OneDrive, Outlook/Calendar) require a connected Microsoft 365 account. <Link to="/settings" className="underline">Connect Microsoft 365</Link> or <Link to="/get-started" className="underline">Get Started</Link>.
        </div>
      )}

      <div className="grid gap-3 text-sm">
        <div>
          <label className="text-xs block mb-1">URL (Procore homepage, SharePoint site/folder/share-link, OneDrive)</label>
          <input
            className="w-full bg-[var(--hb-bg)] border border-[var(--hb-border)] rounded px-2 py-1 text-sm"
            value={url}
            onChange={(e) => { setUrl(e.target.value); resetPreview(); }}
            placeholder="https://app.procore.com/123456/project/home  or  https://...sharepoint.com/sites/...  or  https://...my.sharepoint.com/personal/..."
            disabled={busy !== null}
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="text-xs block mb-1">Project key (optional)</label>
            <input
              className="w-full bg-[var(--hb-bg)] border border-[var(--hb-border)] rounded px-2 py-1 text-sm"
              value={projectKey}
              onChange={(e) => setProjectKey(e.target.value)}
              placeholder="proj-abc"
            />
          </div>
          <div>
            <label className="text-xs block mb-1">Source name (optional)</label>
            <input
              className="w-full bg-[var(--hb-bg)] border border-[var(--hb-border)] rounded px-2 py-1 text-sm"
              value={sourceName}
              onChange={(e) => setSourceName(e.target.value)}
              placeholder="Project Documents"
            />
          </div>
        </div>

        <div>
          <label className="text-xs block mb-1">OneDrive scope (when applicable)</label>
          <select
            className="bg-[var(--hb-bg)] border border-[var(--hb-border)] rounded px-2 py-1 text-sm"
            value={scopeMode}
            onChange={(e) => { setScopeMode(e.target.value); resetPreview(); }}
          >
            <option value="">(default / not specified)</option>
            <option value="selected_folders">selected_folders (provide IDs below)</option>
            <option value="all_folders_explicit">all_folders_explicit (large scope warning)</option>
            <option value="excluded">excluded (disabled source)</option>
          </select>
          {scopeMode === 'selected_folders' && (
            <input
              className="mt-1 w-full bg-[var(--hb-bg)] border border-[var(--hb-border)] rounded px-2 py-1 text-sm font-mono"
              placeholder="folder-item-id-1, folder-item-id-2"
              value={selectedIds}
              onChange={(e) => setSelectedIds(e.target.value)}
            />
          )}
        </div>

        <div className="flex flex-wrap gap-4 text-xs">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={includeOutlook} onChange={(e) => { setIncludeOutlook(e.target.checked); resetPreview(); }} />
            Include Outlook (project_matching_only=false by default)
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={includeCalendar} onChange={(e) => { setIncludeCalendar(e.target.checked); resetPreview(); }} />
            Include Calendar (project_matching_only=false by default)
          </label>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <button
          className="badge"
          onClick={doPreview}
          disabled={busy !== null || (!url && !includeOutlook && !includeCalendar)}
        >
          {busy === 'preview' ? 'Previewing…' : 'Preview'}
        </button>
        <button className="badge" onClick={refreshList} disabled={busy !== null}>Refresh list</button>
      </div>

      <ErrorState message={previewError} onRetry={doPreview} />
      <ErrorState message={listError} onRetry={refreshList} />

      {preview && (
        <ConnectionPreviewCard
          preview={preview}
          onSave={doSave}
          saving={busy === 'save'}
          saveError={saveError}
        />
      )}

      {/* Current connections / pending approvals */}
      <div className="mt-4">
        <div className="text-xs font-medium mb-1">Saved connections / first-sync status</div>
        {pendingItems.length === 0 && (
          <div className="text-xs text-[var(--hb-muted)]">No saved connections yet. Preview and save above.</div>
        )}
        {pendingItems.length > 0 && (
          <div className="text-xs space-y-1">
            {pendingItems.map((it: any, idx: number) => (
              <div key={idx} className="border border-[var(--hb-border)] rounded p-2">
                <div>
                  <span className="font-mono">{it.connection_id || it.source_id || it.id}</span>
                  {' '}<span className="badge">{it.source_type || it.detected_source_type || 'source'}</span>
                  {' '}<span className="badge">{it.first_sync_status || it.sync_status || 'unknown'}</span>
                  {it.admin_approval_required && <span className="badge badge-stale ml-1">admin approval required</span>}
                </div>
                {it.project_key && <div>project_key: {it.project_key}</div>}
                {it.source_name && <div>source: {it.source_name}</div>}
              </div>
            ))}
          </div>
        )}
        <div className="text-[10px] text-[var(--hb-muted)] mt-1">
          Statuses reflect local configuration only. Live sync requires separate admin approval via Admin surfaces.
        </div>
      </div>

      <div className="advisory mt-3">
        All operations are local-first and advisory. Preview/save do not contact external sources for content and never start sync.
        Outlook/Calendar project matching is optional and false by default (index safely, match after ingestion).
      </div>
    </div>
  );
}
