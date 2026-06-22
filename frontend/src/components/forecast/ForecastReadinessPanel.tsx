import { ShieldAlert } from 'lucide-react'
import { getLocalUiRole } from '../../lib/api'
import { useForecastReadiness } from '../../hooks/useForecastReadiness'
import { ForecastAdvisoryStrip } from './ForecastPrimitives'
import { ForecastActionLink } from './ForecastPageChrome'
import { BLOCKER_COPY, READ_ROOTS, ROOT_LABELS, rootAdvisory } from './forecastRuntimeCopy'
import type { RuntimeRootStatus } from './forecastRuntimeCopy'
import { ForecastStatusPill } from './ForecastStatusPill'

const WORKSPACE_ROWS = [
  ...READ_ROOTS,
  { key: 'runs_root', label: ROOT_LABELS.runs_root, unlocks: 'Generation history' },
  { key: 'eval_root', label: ROOT_LABELS.eval_root, unlocks: 'External evaluation' },
  { key: 'config_edit_root', label: ROOT_LABELS.config_edit_root, unlocks: 'Configuration proposals' },
]

export function ForecastReadinessPanel() {
  const { data, isLoading } = useForecastReadiness()
  const role = getLocalUiRole()
  const canRepair = role === 'operator' || role === 'admin'

  if (isLoading || !data) return null

  const roots = (data.roots || {}) as Record<string, RuntimeRootStatus>
  const allReady = WORKSPACE_ROWS.every((r) => roots[r.key]?.valid)
  if (allReady) return null

  const appManaged = data.storage_mode !== 'custom'

  return (
    <section className="forecast-panel border-amber-700/30 bg-gradient-to-br from-amber-950/20 to-[var(--hb-surface)]">
      <div className="forecast-panel-header">
        <div className="forecast-panel-icon text-amber-300 border-amber-700/40 bg-amber-950/30">
          <ShieldAlert size={16} strokeWidth={2} aria-hidden />
        </div>
        <div>
          <h2 className="forecast-section-label">Forecast readiness</h2>
          <p className="text-sm text-[var(--hb-muted)] mt-1 leading-relaxed">
            {appManaged
              ? 'HB manages local forecast storage on this machine. Review readiness or repair missing workspaces before generating.'
              : 'Custom storage locations are in use. Confirm readiness before generating forecasts.'}
          </p>
        </div>
      </div>

      <ul className="forecast-checklist">
        {WORKSPACE_ROWS.map((r) => {
          const root = roots[r.key]
          const ok = Boolean(root?.valid)
          const detail = ok
            ? rootAdvisory(r.key, root) || 'Ready'
            : `${BLOCKER_COPY[root?.blocker || ''] || 'Not ready'} — ${r.unlocks}`
          return (
            <li key={r.key} className={`forecast-checklist-item ${ok ? 'is-ready' : ''}`}>
              <div className="min-w-0">
                <div className="text-sm font-medium">{r.label}</div>
                <div className="text-xs text-[var(--hb-muted)] mt-0.5">{detail}</div>
              </div>
              <ForecastStatusPill status={ok ? 'validated' : 'attention'} />
            </li>
          )
        })}
      </ul>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <ForecastActionLink to="/forecasting/runtime" variant="primary">
          {canRepair ? 'Open storage settings' : 'View storage settings'}
        </ForecastActionLink>
        <ForecastAdvisoryStrip>Advisory only — no live writeback</ForecastAdvisoryStrip>
      </div>
    </section>
  )
}