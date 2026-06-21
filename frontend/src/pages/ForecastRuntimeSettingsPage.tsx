/* eslint-disable @typescript-eslint/no-explicit-any */
/* Forecasting — Runtime Settings (Implementation Phase 6).
 * Lets an operator/admin wire the forecast data roots into the live app. The status view is
 * redaction-safe (booleans + plain-language blockers, never paths) and visible to any role; the
 * raw configured paths are loaded only for an admin (the documented admin-only echo). Saving
 * validates fail-closed on the backend (a write folder under the live data folder is refused). */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { StatusPill } from './ForecastingPage'
import { api, getLocalUiRole } from '../lib/api'

const ROOT_LABELS: Record<string, string> = {
  package_roots: 'Forecast packages',
  data_root: 'Source data folder',
  runs_root: 'Run output folder',
  eval_root: 'Evaluation output folder',
  db_path: 'Source database',
  cfr_src: 'Engine source',
  config_edit_root: 'Config proposal output folder',
}

const BLOCKER_COPY: Record<string, string> = {
  not_configured: 'Not configured',
  not_absolute: 'Path must be absolute',
  missing: 'Path does not exist',
  not_a_directory: 'Not a directory',
  under_live_data_root: 'Must be outside the live data folder',
  not_creatable: 'Folder cannot be created',
}

const PATH_FIELDS: { key: string; label: string; placeholder: string }[] = [
  { key: 'data_root', label: 'Source data folder', placeholder: 'Absolute path to the live forecast data folder' },
  { key: 'runs_root', label: 'Run output folder', placeholder: 'Absolute path (must be OUTSIDE the source data folder)' },
  { key: 'eval_root', label: 'Evaluation output folder', placeholder: 'Absolute path (must be OUTSIDE the source data folder)' },
  { key: 'db_path', label: 'Source database', placeholder: 'Absolute path to the read-only source database' },
  { key: 'cfr_src', label: 'Engine source', placeholder: 'Optional — defaults to the bundled engine' },
  { key: 'config_edit_root', label: 'Config proposal output folder', placeholder: 'Absolute path (must be OUTSIDE the source data folder)' },
]

export function ForecastRuntimeSettingsPage() {
  const role = getLocalUiRole()
  const canEdit = role === 'operator' || role === 'admin'
  const isAdmin = role === 'admin'

  const { data: statusResp, isLoading, error, refetch } = useQuery({
    queryKey: ['forecast', 'runtime', 'status'],
    queryFn: () => api.getForecastRuntimeStatus(),
  })

  // Admin-only raw-path echo to pre-fill the form (the single deliberate path-bearing payload).
  const { data: configResp } = useQuery({
    queryKey: ['forecast', 'runtime', 'config'],
    queryFn: () => api.getForecastRuntimeConfig(),
    enabled: isAdmin,
  })

  const [form, setForm] = useState<Record<string, string>>({})
  const [packageRoots, setPackageRoots] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    const cfg = configResp?.config
    if (!cfg) return
    const next: Record<string, string> = {}
    for (const { key } of PATH_FIELDS) next[key] = cfg[key] ?? ''
    setForm(next)
    setPackageRoots(Array.isArray(cfg.package_roots) ? cfg.package_roots.join('\n') : '')
  }, [configResp])

  async function onSave() {
    setSaving(true)
    setSaveError(null)
    setSaved(false)
    try {
      const payload: Record<string, any> = {}
      for (const { key } of PATH_FIELDS) {
        const v = (form[key] || '').trim()
        if (v) payload[key] = v
      }
      const roots = packageRoots
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean)
      if (roots.length) payload.package_roots = roots
      await api.saveForecastRuntimeConfig(payload)
      setSaved(true)
      await refetch()
    } catch (e: any) {
      const message: string = String(e?.message || '')
      setSaveError(
        message.includes('forecast_runtime_invalid')
          ? 'One or more folders are invalid (a run/evaluation folder may not sit inside the source data folder).'
          : 'The runtime configuration could not be saved.',
      )
    } finally {
      setSaving(false)
    }
  }

  const roots: Record<string, any> = statusResp?.roots || {}
  const surfaces: Record<string, boolean> = statusResp?.surfaces_ready || {}

  return (
    <div>
      <div className="text-xs mb-2">
        <Link to="/forecasting" className="underline">
          ← Back to forecast packages
        </Link>
      </div>

      <div className="card">
        <div className="section-title">Runtime data sources</div>
        <p className="text-sm text-[var(--hb-muted)]">
          Configure where the app reads forecast data and writes isolated run/evaluation output.
          These settings make the forecast surfaces serve real project data. The live data folder is
          never written.
        </p>
        {isLoading ? (
          <div className="text-sm text-[var(--hb-muted)] mt-2">Loading status…</div>
        ) : error ? (
          <p className="text-sm text-rose-300 mt-2">Status is unavailable right now.</p>
        ) : (
          <div className="overflow-x-auto mt-2">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-left text-[var(--hb-muted)] border-b border-[var(--hb-border)]">
                  <th className="py-2 pr-3">Data source</th>
                  <th className="py-2 pr-3">Status</th>
                  <th className="py-2 pr-3">Detail</th>
                </tr>
              </thead>
              <tbody>
                {Object.keys(ROOT_LABELS).map((key) => {
                  const r = roots[key] || {}
                  return (
                    <tr key={key} className="border-b border-[var(--hb-border)]">
                      <td className="py-2 pr-3">{ROOT_LABELS[key]}</td>
                      <td className="py-2 pr-3">
                        <StatusPill status={r.valid ? 'validated' : 'attention'} />
                      </td>
                      <td className="py-2 pr-3 text-[var(--hb-muted)]">
                        {r.valid
                          ? 'Ready'
                          : BLOCKER_COPY[r.blocker as string] || 'Not configured'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card mt-3">
        <div className="section-title">Surfaces ready</div>
        <div className="flex flex-wrap gap-2 text-sm">
          {['catalog', 'config', 'run_center', 'external_eval', 'config_edit'].map((k) => (
            <span key={k} className="flex items-center gap-1">
              <StatusPill status={surfaces[k] ? 'validated' : 'attention'} />
              <span className="text-[var(--hb-muted)]">{k.replace('_', ' ')}</span>
            </span>
          ))}
        </div>
      </div>

      {canEdit && (
        <div className="card mt-3">
          <div className="section-title">Edit data sources</div>
          {!isAdmin && (
            <p className="text-xs text-[var(--hb-muted)] mb-2">
              Current paths are hidden for your role. Enter a full path to set or change a source.
            </p>
          )}
          <div className="grid gap-3">
            <label className="text-sm">
              <span className="block mb-1">Forecast packages (one absolute path per line)</span>
              <textarea
                value={packageRoots}
                onChange={(e) => setPackageRoots(e.target.value)}
                rows={2}
                className="w-full rounded border border-[var(--hb-border)] bg-transparent px-2 py-1 text-sm"
                placeholder="Absolute path(s) to the forecast package folder(s)"
              />
            </label>
            {PATH_FIELDS.map(({ key, label, placeholder }) => (
              <label key={key} className="text-sm">
                <span className="block mb-1">{label}</span>
                <input
                  type="text"
                  value={form[key] || ''}
                  onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                  className="w-full rounded border border-[var(--hb-border)] bg-transparent px-2 py-1 text-sm"
                  placeholder={placeholder}
                />
              </label>
            ))}
          </div>
          <div className="flex items-center gap-3 mt-3">
            <button
              type="button"
              onClick={onSave}
              disabled={saving}
              className="rounded border border-[var(--hb-accent)] px-3 py-1.5 text-sm disabled:opacity-50"
            >
              {saving ? 'Saving…' : 'Save data sources'}
            </button>
            {saved && <span className="text-sm text-emerald-300">Saved.</span>}
            {saveError && <span className="text-sm text-rose-300">{saveError}</span>}
          </div>
        </div>
      )}
    </div>
  )
}
