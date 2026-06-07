/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState } from 'react';
import { useConnectionsAccounts } from '../../hooks/useOnboardingReadiness';
import {
  previewProjectConnection,
  saveProjectConnection,
  getProjectConnections,
} from '../../lib/api';
import { ErrorState } from '../ui/ErrorState';
import { ConnectionPreviewCard } from './ConnectionPreviewCard';

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
      <h3 className="font-medium mb-2">Project Connections</h3>

      <div className="text-xs mb-3">
        Review and save the project information this app should watch. Saving selections does not start updates.
      </div>

      {/* Auth gating messages */}
      {!procoreOk && (
        <div className="text-xs mb-1 text-amber-600">
          Procore sources require a connected Procore account. <a href="/settings" className="underline">Connect Procore</a> or <a href="/get-started" className="underline">Get Started</a>.
        </div>
      )}
      {!graphOk && (
        <div className="text-xs mb-1 text-amber-600">
          Microsoft project sources require a connected Microsoft 365 account. <a href="/settings" className="underline">Connect Microsoft 365</a> or <a href="/get-started" className="underline">Get Started</a>.
        </div>
      )}

      <div className="grid gap-3 text-sm">
        <div>
          <label className="text-xs block mb-1">Project or folder link</label>
          <input
            className="w-full bg-[var(--hb-bg)] border border-[var(--hb-border)] rounded px-2 py-1 text-sm"
            value={url}
            onChange={(e) => { setUrl(e.target.value); resetPreview(); }}
            placeholder="Paste a project or folder link"
            disabled={busy !== null}
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="text-xs block mb-1">Project name (optional)</label>
            <input
              className="w-full bg-[var(--hb-bg)] border border-[var(--hb-border)] rounded px-2 py-1 text-sm"
              value={projectKey}
              onChange={(e) => setProjectKey(e.target.value)}
              placeholder="Project name"
            />
          </div>
          <div>
            <label className="text-xs block mb-1">Connection name (optional)</label>
            <input
              className="w-full bg-[var(--hb-bg)] border border-[var(--hb-border)] rounded px-2 py-1 text-sm"
              value={sourceName}
              onChange={(e) => setSourceName(e.target.value)}
              placeholder="Project Documents"
            />
          </div>
        </div>

        <div>
          <label className="text-xs block mb-1">Folder selection</label>
          <select
            className="bg-[var(--hb-bg)] border border-[var(--hb-border)] rounded px-2 py-1 text-sm"
            value={scopeMode}
            onChange={(e) => { setScopeMode(e.target.value); resetPreview(); }}
          >
            <option value="">Use detected folder</option>
            <option value="selected_folders">Selected folders</option>
            <option value="all_folders_explicit">All folders</option>
            <option value="excluded">Do not include this source</option>
          </select>
          {scopeMode === 'selected_folders' && (
            <input
              className="mt-1 w-full bg-[var(--hb-bg)] border border-[var(--hb-border)] rounded px-2 py-1 text-sm font-mono"
              placeholder="Folder identifiers, separated by commas"
              value={selectedIds}
              onChange={(e) => setSelectedIds(e.target.value)}
            />
          )}
        </div>

        <div className="flex flex-wrap gap-4 text-xs">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={includeOutlook} onChange={(e) => { setIncludeOutlook(e.target.checked); resetPreview(); }} />
            Include email
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={includeCalendar} onChange={(e) => { setIncludeCalendar(e.target.checked); resetPreview(); }} />
            Include calendar
          </label>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <button
          className="badge"
          onClick={doPreview}
          disabled={busy !== null || (!url && !includeOutlook && !includeCalendar)}
        >
          {busy === 'preview' ? 'Checking...' : 'Review project connections'}
        </button>
        <button className="badge" onClick={refreshList} disabled={busy !== null}>Check saved selections</button>
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
        <div className="text-xs font-medium mb-1">Saved project selections</div>
        {pendingItems.length === 0 && (
          <div className="text-xs text-[var(--hb-muted)]">No saved project selections yet.</div>
        )}
        {pendingItems.length > 0 && (
          <div className="text-xs space-y-1">
            {pendingItems.map((it: any, idx: number) => (
              <div key={idx} className="border border-[var(--hb-border)] rounded p-2">
                <div>
                  <span className="font-medium">{it.source_name || it.project_name || it.project_key || it.connection_id || it.source_id || it.id || 'Project selection'}</span>
                  {' '}<span className="badge">{labelSource(it.source_type || it.detected_source_type)}</span>
                  {' '}<span className="badge">{labelStatus(it.first_sync_status || it.sync_status)}</span>
                  {it.admin_approval_required && <span className="badge badge-stale ml-1">Request update approval</span>}
                </div>
                {it.project_key && !it.project_name && <div>Project: {it.project_key}</div>}
              </div>
            ))}
          </div>
        )}
        <div className="text-[10px] text-[var(--hb-muted)] mt-1">
          Saved selections wait for update approval before new data appears.
        </div>
      </div>

      <div className="advisory mt-3">
        Reviewing or saving project selections does not start updates.
      </div>
    </div>
  );
}

function labelSource(value: unknown) {
  const text = String(value || 'source').replace(/_/g, ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

function labelStatus(value: unknown) {
  const status = String(value || 'unknown')
  if (status.includes('pending')) return 'Waiting for update approval'
  if (status.includes('approved')) return 'Approved'
  if (status.includes('rejected')) return 'Needs review'
  if (status === 'unknown') return 'Status unavailable'
  return status.replace(/_/g, ' ')
}
