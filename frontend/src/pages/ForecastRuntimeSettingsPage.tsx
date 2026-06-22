/* Forecast storage & database readiness — app-managed by default; advanced overrides admin-only. */
import { Database, Layers } from 'lucide-react'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { AdminPathOverrideForm } from '../components/forecast/AdminPathOverrideForm'
import {
  ForecastActionButton,
  ForecastBackLink,
  ForecastChecklistItem,
  ForecastPageHeader,
  ForecastShell,
  ForecastSubnav,
} from '../components/forecast/ForecastPageChrome'
import { ForecastPanel } from '../components/forecast/ForecastPrimitives'
import { ForecastStatusPill } from '../components/forecast/ForecastStatusPill'
import { BLOCKER_COPY, ROOT_LABELS, SURFACE_LABELS } from '../components/forecast/forecastRuntimeCopy'
import { api, getLocalUiRole } from '../lib/api'

const STORAGE_ROWS = [
  'db_path',
  'package_roots',
  'data_root',
  'runs_root',
  'eval_root',
  'config_edit_root',
] as const

export function ForecastRuntimeSettingsPage() {
  const role = getLocalUiRole()
  const canRepair = role === 'operator' || role === 'admin'
  const isAdmin = role === 'admin'

  const { data: statusResp, isLoading, error, refetch } = useQuery({
    queryKey: ['forecast', 'runtime', 'status'],
    queryFn: () => api.getForecastRuntimeStatus(),
  })

  const { data: configResp } = useQuery({
    queryKey: ['forecast', 'runtime', 'config'],
    queryFn: () => api.getForecastRuntimeConfig(),
    enabled: isAdmin,
  })

  const [repairing, setRepairing] = useState(false)
  const [repairError, setRepairError] = useState<string | null>(null)
  const [repairDone, setRepairDone] = useState(false)
  const [advancedOpen, setAdvancedOpen] = useState(false)

  async function onRepair() {
    setRepairing(true)
    setRepairError(null)
    setRepairDone(false)
    try {
      await api.repairForecastRuntimeStorage()
      setRepairDone(true)
      await refetch()
    } catch {
      setRepairError('Local storage could not be repaired right now.')
    } finally {
      setRepairing(false)
    }
  }

  const roots = (statusResp?.roots || {}) as Record<string, { valid?: boolean; blocker?: string }>
  const surfaces = (statusResp?.surfaces_ready || {}) as Record<string, boolean>
  const appManaged = statusResp?.storage_mode !== 'custom'
  const allStorageReady = STORAGE_ROWS.every((k) => roots[k]?.valid)

  return (
    <ForecastShell>
      <ForecastBackLink />
      <ForecastSubnav />

      <section className="forecast-panel">
        <ForecastPageHeader
          title="Storage & database readiness"
          subtitle="HB manages local forecast folders and the database on this machine. You do not need to configure locations during normal setup."
        />
        <p className="text-xs text-[var(--hb-muted)] mt-3">
          Mode: <span className="font-medium text-[var(--hb-text)]">{appManaged ? 'Managed by HB' : 'Custom locations'}</span>
          {allStorageReady && appManaged && (
            <span className="text-emerald-300 ml-2">· All workspaces ready</span>
          )}
        </p>

        {isLoading ? (
          <div className="text-sm text-[var(--hb-muted)] mt-3">Loading readiness…</div>
        ) : error ? (
          <p className="text-sm text-rose-300 mt-3">Readiness is unavailable right now.</p>
        ) : (
          <ul className="forecast-checklist">
            {STORAGE_ROWS.map((key) => {
              const r = roots[key] || {}
              const ok = Boolean(r.valid)
              return (
                <ForecastChecklistItem
                  key={key}
                  label={ROOT_LABELS[key]}
                  detail={ok ? 'Ready' : BLOCKER_COPY[r.blocker || ''] || 'Not ready'}
                  ready={ok}
                  trailing={<ForecastStatusPill status={ok ? 'validated' : 'attention'} />}
                />
              )
            })}
          </ul>
        )}

        {canRepair && (
          <div className="flex flex-wrap items-center gap-3 mt-4">
            <ForecastActionButton onClick={onRepair} disabled={repairing}>
              {repairing ? 'Repairing…' : 'Repair local storage'}
            </ForecastActionButton>
            {repairDone && <span className="text-sm text-emerald-300">Repaired.</span>}
            {repairError && <span className="text-sm text-rose-300">{repairError}</span>}
          </div>
        )}
      </section>

      <ForecastPanel icon={Layers} title="Forecast surfaces" description="Each surface unlocks when its storage workspaces are ready. All remain advisory.">
        <div className="flex flex-wrap gap-2">
          {Object.entries(SURFACE_LABELS).map(([k, label]) => (
            <span key={k} className="forecast-surface-chip">
              <ForecastStatusPill status={surfaces[k] ? 'validated' : 'attention'} />
              <span className="text-[var(--hb-muted)]">{label}</span>
            </span>
          ))}
        </div>
      </ForecastPanel>

      {isAdmin && (
        <section className="forecast-panel">
          <button
            type="button"
            onClick={() => setAdvancedOpen((o) => !o)}
            className="forecast-section-label text-left w-full flex items-center gap-2"
            aria-expanded={advancedOpen}
          >
            <Database size={14} aria-hidden />
            Advanced manual path override {advancedOpen ? '▾' : '▸'}
          </button>
          {advancedOpen && configResp?.config && (
            <div className="mt-3">
              <AdminPathOverrideForm
                key={String(configResp.config_file_present)}
                config={configResp.config as Record<string, unknown>}
                onSaved={() => void refetch()}
              />
            </div>
          )}
        </section>
      )}
    </ForecastShell>
  )
}