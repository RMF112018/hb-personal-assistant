import { useState } from 'react'

import { api } from '../../lib/api'

const PATH_FIELDS: { key: string; label: string; placeholder: string }[] = [
  { key: 'data_root', label: 'Source data workspace', placeholder: 'Absolute path to source data (advanced)' },
  { key: 'runs_root', label: 'Run output workspace', placeholder: 'Absolute path outside source data' },
  { key: 'eval_root', label: 'Evaluation workspace', placeholder: 'Absolute path outside source data' },
  { key: 'db_path', label: 'Local forecast database', placeholder: 'Absolute path to SQLite database' },
  { key: 'cfr_src', label: 'Forecast engine', placeholder: 'Optional — defaults to bundled engine' },
  { key: 'config_edit_root', label: 'Config proposal workspace', placeholder: 'Absolute path outside source data' },
]

export type AdminRuntimeConfig = Record<string, unknown>

function buildInitialForm(config: AdminRuntimeConfig) {
  const form: Record<string, string> = {}
  for (const { key } of PATH_FIELDS) {
    const v = config[key]
    form[key] = typeof v === 'string' ? v : ''
  }
  const roots = config.package_roots
  const packageRoots = Array.isArray(roots) ? roots.filter((x): x is string => typeof x === 'string').join('\n') : ''
  return { form, packageRoots }
}

export function AdminPathOverrideForm({
  config,
  onSaved,
}: {
  config: AdminRuntimeConfig
  onSaved: () => void
}) {
  const initial = buildInitialForm(config)
  const [form, setForm] = useState(initial.form)
  const [packageRoots, setPackageRoots] = useState(initial.packageRoots)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [resetError, setResetError] = useState<string | null>(null)

  async function onSave() {
    setSaving(true)
    setSaveError(null)
    setSaved(false)
    try {
      const payload: Record<string, string | string[]> = {}
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
      onSaved()
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : ''
      setSaveError(
        message.includes('forecast_runtime_invalid')
          ? 'One or more locations are invalid. Output workspaces must stay outside the source data workspace.'
          : 'Overrides could not be saved.',
      )
    } finally {
      setSaving(false)
    }
  }

  async function onReset() {
    if (
      !window.confirm(
        'Reset all forecast storage to app-managed defaults? Custom locations will be replaced.',
      )
    ) {
      return
    }
    setResetting(true)
    setResetError(null)
    try {
      await api.resetForecastRuntimeDefaults()
      onSaved()
    } catch {
      setResetError('Could not reset to app-managed defaults.')
    } finally {
      setResetting(false)
    }
  }

  return (
    <>
      <p className="text-sm text-amber-200/90 mt-2 rounded border border-amber-700/40 bg-amber-950/20 px-3 py-2">
        Admin only. Manual path overrides are for development, migration, or support — not normal
        setup. The app manages storage automatically.
      </p>
      <div className="grid gap-3 mt-3">
        <label className="text-sm">
          <span className="block mb-1">Forecast package storage (one absolute path per line)</span>
          <textarea
            value={packageRoots}
            onChange={(e) => setPackageRoots(e.target.value)}
            rows={2}
            className="w-full rounded border border-[var(--hb-border)] bg-transparent px-2 py-1 text-sm"
            placeholder="Advanced override only"
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
      <div className="flex flex-wrap items-center gap-3 mt-3">
        <button
          type="button"
          onClick={onSave}
          disabled={saving}
          className="rounded border border-[var(--hb-accent)] px-3 py-1.5 text-sm disabled:opacity-50"
        >
          {saving ? 'Saving…' : 'Save overrides'}
        </button>
        <button
          type="button"
          onClick={onReset}
          disabled={resetting}
          className="rounded border border-rose-400/60 px-3 py-1.5 text-sm text-rose-200 disabled:opacity-50"
        >
          {resetting ? 'Resetting…' : 'Reset to app-managed defaults'}
        </button>
        {saved && <span className="text-sm text-emerald-300">Saved.</span>}
        {saveError && <span className="text-sm text-rose-300">{saveError}</span>}
        {resetError && <span className="text-sm text-rose-300">{resetError}</span>}
      </div>
    </>
  )
}