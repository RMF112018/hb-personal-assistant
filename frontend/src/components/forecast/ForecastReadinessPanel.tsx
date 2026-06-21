/* eslint-disable @typescript-eslint/no-explicit-any */
/* Forecast read-root onboarding — a guided readiness panel shown on the Forecasting landing when the
 * read data sources are not configured. Redaction-safe: it renders only the status booleans, coded
 * blocker copy, and integer advisory counts the backend returns (never a path). Links to the existing
 * runtime settings page for the actual editing. */
import { Link } from 'react-router-dom'

import { getLocalUiRole } from '../../lib/api'
import { useForecastReadiness } from '../../hooks/useForecastReadiness'
import { BLOCKER_COPY, READ_ROOTS, rootAdvisory } from './forecastRuntimeCopy'

function Dot({ ok }: { ok: boolean }) {
  return (
    <span
      aria-hidden
      className={`inline-block h-2 w-2 rounded-full ${ok ? 'bg-emerald-400' : 'bg-amber-400'}`}
    />
  )
}

export function ForecastReadinessPanel() {
  const { data, isLoading } = useForecastReadiness()
  const role = getLocalUiRole()
  const canEdit = role === 'operator' || role === 'admin'

  if (isLoading || !data) return null

  const roots: Record<string, any> = data.roots || {}
  const allReady = READ_ROOTS.every((r) => roots[r.key]?.valid)
  if (allReady) return null // nothing to onboard — surfaces are configured

  return (
    <div className="card">
      <div className="section-title">Set up forecast data sources</div>
      <p className="text-sm text-[var(--hb-muted)]">
        Point the app at your project's forecast inputs to unlock the forecasting surfaces. The live
        project data is only read — it is never modified.
      </p>

      <ul className="mt-3 grid gap-2 text-sm">
        {READ_ROOTS.map((r) => {
          const root = roots[r.key] || {}
          const ok = Boolean(root.valid)
          const detail = ok
            ? rootAdvisory(r.key, root) || 'Ready'
            : `${BLOCKER_COPY[root.blocker as string] || 'Not configured'} — ${r.unlocks}`
          return (
            <li key={r.key} className="flex items-start gap-2">
              <span className="mt-1.5">
                <Dot ok={ok} />
              </span>
              <span>
                <span className="font-medium">{r.label}</span>
                <span className="text-[var(--hb-muted)]"> — {detail}</span>
              </span>
            </li>
          )
        })}
      </ul>

      <div className="mt-3">
        <Link
          to="/forecasting/runtime"
          className="inline-block rounded border border-[var(--hb-accent)] px-3 py-1.5 text-sm"
        >
          {canEdit ? 'Configure data sources' : 'View data source setup'}
        </Link>
      </div>
    </div>
  )
}
