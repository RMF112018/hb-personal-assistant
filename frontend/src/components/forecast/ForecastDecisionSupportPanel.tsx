/* Persisted forecast run-output + decision-support (Phase 5).
 * Read-only DB read-model surface: confidence, project maturity, data-availability ("missing data"),
 * method eligibility, and per-code recommendations. Navigates by the hash-based output_id; renders
 * gracefully empty until the authorized live-write has populated the tables. */
import { useQuery } from '@tanstack/react-query'
import { Gauge } from 'lucide-react'

import { EmptyState } from '../ui/EmptyState'
import { api } from '../../lib/api'
import {
  ForecastAdvisoryStrip,
  ForecastChecklistItem,
  ForecastPanel,
  ForecastTable,
  ForecastTd,
  ForecastTh,
} from './ForecastPrimitives'
import { ForecastStatusPill } from './ForecastStatusPill'

function money(v: string | null | undefined): string {
  return v == null || v === '' ? '—' : v
}

function availabilityPill(a: string | null): string {
  if (a === 'available') return 'validated'
  if (a === 'partial') return 'attention'
  return 'unsupported'
}
function confidencePill(label: string | null | undefined): string {
  if (label === 'high') return 'validated'
  if (label === 'moderate' || label === 'medium' || label === 'moderate-high') return 'attention'
  if (label === 'low' || label === 'none' || label === 'very low') return 'invalid'
  return 'unknown'
}
function methodPill(status: string | null): string {
  if (status?.startsWith('eligible')) return 'validated'
  if (status?.startsWith('downgraded')) return 'attention'
  if (status?.startsWith('rejected')) return 'invalid'
  return 'unsupported'
}

/** Decision-support detail panel (recommendations, data availability, method eligibility) for the
 * page-owned active output. Headline KPI cards live in the consolidated Forecast Summary; this panel
 * is detail-only. v66 decision-support emptiness is neutral here (subsections omit) — never an error
 * and never a poison for the v63-sourced summary. */
export function ForecastDecisionSupportPanel({
  project,
  activeOutputId,
}: {
  project: string
  activeOutputId?: string
}) {
  const { data: list, isLoading, error } = useQuery({
    queryKey: ['forecast', 'db-outputs', project],
    queryFn: () => api.getForecastDbOutputs(project),
  })
  const outputs = list?.outputs ?? []
  const activeId = activeOutputId ?? outputs[0]?.output_id

  const { data: detail } = useQuery({
    queryKey: ['forecast', 'db-output', activeId],
    queryFn: () => api.getForecastDbOutput(activeId as string),
    enabled: Boolean(activeId),
  })
  const { data: ds } = useQuery({
    queryKey: ['forecast', 'db-decision-support', activeId],
    queryFn: () => api.getForecastDbDecisionSupport(activeId as string),
    enabled: Boolean(activeId),
  })

  if (error) {
    return (
      <ForecastPanel icon={Gauge} title="Decision support">
        <ForecastAdvisoryStrip>
          Forecast database not available. Decision-support detail appears here once configured.
        </ForecastAdvisoryStrip>
      </ForecastPanel>
    )
  }
  if (!isLoading && outputs.length === 0) {
    return (
      <ForecastPanel icon={Gauge} title="Decision support">
        <EmptyState
          title="No persisted forecast outputs yet"
          hint="Generate a forecast for this project to populate recommendations and decision support."
        />
      </ForecastPanel>
    )
  }

  const hasDecisionSupport = Boolean(
    ds && (ds.data_availability.length > 0 || ds.method_eligibility.length > 0),
  )

  return (
    <ForecastPanel
      icon={Gauge}
      title="Decision support"
      description="Read-only recommendations, data availability, and method eligibility from the local database."
    >
      {detail && !hasDecisionSupport && (
        <p className="text-sm text-[var(--hb-muted)]">
          Decision-support scoring is not populated for this output. Recommendations below come from the
          persisted forecast.
        </p>
      )}

      {ds && ds.data_availability.length > 0 && (
        <div className="mt-4">
          <h3 className="forecast-eyebrow mb-2">Data availability</h3>
          <ul className="space-y-1">
            {ds.data_availability.map((d) => (
              <ForecastChecklistItem
                key={d.domain}
                label={d.domain}
                detail={d.reason ?? undefined}
                ready={d.availability === 'available'}
                trailing={<ForecastStatusPill status={availabilityPill(d.availability)} />}
              />
            ))}
          </ul>
        </div>
      )}

      {ds && ds.method_eligibility.length > 0 && (
        <div className="mt-4">
          <h3 className="forecast-eyebrow mb-2">Method eligibility</h3>
          <ForecastTable
            headers={
              <>
                <ForecastTh>Method</ForecastTh>
                <ForecastTh>Status</ForecastTh>
                <ForecastTh>Weight</ForecastTh>
              </>
            }
          >
            {ds.method_eligibility.map((m) => (
              <tr key={m.method}>
                <ForecastTd>{m.method}</ForecastTd>
                <ForecastTd>
                  <ForecastStatusPill status={methodPill(m.status)} />
                </ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">{m.weight ?? '—'}</ForecastTd>
              </tr>
            ))}
          </ForecastTable>
        </div>
      )}

      {detail && detail.budget_codes.length > 0 && (
        <div className="mt-4">
          <h3 className="forecast-eyebrow mb-2">
            Recommendations · {detail.budget_codes.length} codes · {detail.risks.length} risks
          </h3>
          <ForecastTable
            headers={
              <>
                <ForecastTh>Cost code</ForecastTh>
                <ForecastTh>Action</ForecastTh>
                <ForecastTh>Confidence</ForecastTh>
                <ForecastTh>Recommended cost</ForecastTh>
              </>
            }
          >
            {detail.budget_codes.slice(0, 50).map((b, i) => (
              <tr key={b.budget_code_key ?? `bc-${i}`}>
                <ForecastTd>{b.cost_code ?? b.budget_code_key ?? '—'}</ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">{b.forecast_action ?? '—'}</ForecastTd>
                <ForecastTd>
                  <ForecastStatusPill status={confidencePill(b.confidence)} />
                </ForecastTd>
                <ForecastTd className="tabular-nums">{money(b.recommended_projected_cost)}</ForecastTd>
              </tr>
            ))}
          </ForecastTable>
        </div>
      )}

      {detail && detail.commitment_exposure.length > 0 && (
        <div className="mt-4">
          <h3 className="forecast-eyebrow mb-2">Commitment exposure</h3>
          <ForecastTable
            headers={
              <>
                <ForecastTh>Cost code</ForecastTh>
                <ForecastTh>Committed</ForecastTh>
                <ForecastTh>Exposure</ForecastTh>
              </>
            }
          >
            {detail.commitment_exposure.slice(0, 50).map((c, i) => (
              <tr key={c.budget_code_key ?? `ce-${i}`}>
                <ForecastTd>{c.budget_code_key ?? '—'}</ForecastTd>
                <ForecastTd className="tabular-nums">{money(c.committed_amount)}</ForecastTd>
                <ForecastTd className="tabular-nums">{money(c.exposure_amount)}</ForecastTd>
              </tr>
            ))}
          </ForecastTable>
        </div>
      )}

      {detail && detail.schedule_phasing.length > 0 && (
        <div className="mt-4">
          <h3 className="forecast-eyebrow mb-2">Schedule phasing</h3>
          <ForecastTable
            headers={
              <>
                <ForecastTh>Cost code</ForecastTh>
                <ForecastTh>Phase</ForecastTh>
                <ForecastTh>Window</ForecastTh>
                <ForecastTh>Amount</ForecastTh>
              </>
            }
          >
            {detail.schedule_phasing.slice(0, 50).map((s, i) => (
              <tr key={s.budget_code_key ?? `sp-${i}`}>
                <ForecastTd>{s.budget_code_key ?? '—'}</ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">{s.phase ?? '—'}</ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">
                  {s.start_month ?? '—'}–{s.end_month ?? '—'}
                </ForecastTd>
                <ForecastTd className="tabular-nums">{money(s.amount)}</ForecastTd>
              </tr>
            ))}
          </ForecastTable>
        </div>
      )}
    </ForecastPanel>
  )
}
