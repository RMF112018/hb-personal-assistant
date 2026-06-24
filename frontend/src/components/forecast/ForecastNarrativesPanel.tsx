/* Persisted forecast explainability / audit trail (P9, surfacing P8 narratives).
 * Read-only DB read-model surface: per-output reason narratives, human-override audit, source-data
 * QA, and the context→analysis→output package-sha256 lineage chain. Navigates by the hash-based
 * output_id; renders gracefully empty until the authorized live-write has populated the tables.
 * The API curates each narrative (no raw_json, no stamps); this panel only displays it. */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FileText } from 'lucide-react'

import { EmptyState } from '../ui/EmptyState'
import { api } from '../../lib/api'
import {
  ForecastAdvisoryStrip,
  ForecastPanel,
  ForecastTable,
  ForecastTd,
  ForecastTh,
} from './ForecastPrimitives'
import { ForecastSummaryCard, ForecastSummaryGrid } from './ForecastSummary'

function money(v: string | null | undefined): string {
  return v == null || v === '' ? '—' : v
}

/** Persisted explainability / audit-trail panel (hosted in the Run Center). */
export function ForecastNarrativesPanel({ project }: { project: string }) {
  const { data: list, isLoading, error } = useQuery({
    queryKey: ['forecast', 'db-outputs', project],
    queryFn: () => api.getForecastDbOutputs(project),
  })
  const outputs = list?.outputs ?? []
  const [selectedId, setSelectedId] = useState<string | undefined>(undefined)
  const activeId = selectedId ?? outputs[0]?.output_id

  const { data: narr } = useQuery({
    queryKey: ['forecast', 'db-narratives', activeId],
    queryFn: () => api.getForecastDbNarratives(activeId as string),
    enabled: Boolean(activeId),
  })

  if (error) {
    return (
      <ForecastPanel icon={FileText} title="Forecast explainability">
        <ForecastAdvisoryStrip>
          Forecast database not available. Reason narratives and audit trail appear here once configured.
        </ForecastAdvisoryStrip>
      </ForecastPanel>
    )
  }
  if (!isLoading && outputs.length === 0) {
    return (
      <ForecastPanel icon={FileText} title="Forecast explainability">
        <EmptyState
          title="No persisted forecast outputs yet"
          hint="Run the authorized live-write to populate the explainability and audit trail."
        />
      </ForecastPanel>
    )
  }

  const groups = narr?.narratives ?? {}
  const project_narr = groups.project?.[0]
  const overrides = groups.human_override ?? []
  const sourceQa = groups.source_qa?.[0]
  const lineage = groups.lineage?.[0]

  return (
    <ForecastPanel
      icon={FileText}
      title="Forecast explainability"
      description="Read-only reason narratives, human-override audit, and provenance lineage from the local database."
    >
      {outputs.length > 1 && (
        <label className="text-sm text-[var(--hb-muted)] flex items-center gap-2">
          Output
          <select
            className="rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1 text-sm"
            value={activeId}
            onChange={(e) => setSelectedId(e.target.value)}
          >
            {outputs.map((o) => (
              <option key={o.output_id} value={o.output_id}>
                {o.created_display ?? o.output_id}
              </option>
            ))}
          </select>
        </label>
      )}

      {project_narr && (
        <>
          <ForecastSummaryGrid>
            <ForecastSummaryCard
              label="Estimated final cost"
              value={money(project_narr.estimated_final_cost)}
            />
            <ForecastSummaryCard label="Cost to complete" value={money(project_narr.cost_to_complete)} />
            <ForecastSummaryCard
              label="Variance to budget"
              value={money(project_narr.variance_to_budget)}
            />
            <ForecastSummaryCard label="Operator overrides" value={String(project_narr.override_count ?? 0)} />
          </ForecastSummaryGrid>
          {project_narr.narrative && (
            <p className="mt-3 text-sm text-[var(--hb-muted)]">{project_narr.narrative}</p>
          )}
        </>
      )}

      {overrides.length > 0 && (
        <div className="mt-4">
          <h3 className="forecast-eyebrow mb-2">Human overrides · {overrides.length}</h3>
          <ForecastTable
            headers={
              <>
                <ForecastTh>Cost code</ForecastTh>
                <ForecastTh>Field</ForecastTh>
                <ForecastTh>Original → override</ForecastTh>
                <ForecastTh>Delta</ForecastTh>
                <ForecastTh>Applied</ForecastTh>
              </>
            }
          >
            {overrides.slice(0, 50).map((o, i) => (
              <tr key={o.budget_code_key ?? `ho-${i}`}>
                <ForecastTd>{o.budget_code_key ?? '—'}</ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">{o.column ?? '—'}</ForecastTd>
                <ForecastTd className="tabular-nums">
                  {money(o.original)} → {money(o.override)}
                </ForecastTd>
                <ForecastTd className="tabular-nums">{money(o.delta_amount)}</ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">{o.applied_display ?? '—'}</ForecastTd>
              </tr>
            ))}
          </ForecastTable>
        </div>
      )}

      {sourceQa && (
        <div className="mt-4">
          <h3 className="forecast-eyebrow mb-2">Source-data QA</h3>
          <ForecastAdvisoryStrip>
            {sourceQa.narrative ??
              `${sourceQa.null_projected_cost_count ?? 0} null and ${
                sourceQa.zero_projected_cost_count ?? 0
              } zero projected-cost value(s); ${
                sourceQa.duplicate_budget_code_keys?.length ?? 0
              } duplicate budget-code key(s).`}
          </ForecastAdvisoryStrip>
        </div>
      )}

      {lineage && (
        <div className="mt-4">
          <h3 className="forecast-eyebrow mb-2">Package lineage (sha256 chain)</h3>
          <dl className="grid gap-1 text-xs text-[var(--hb-muted)]">
            {([
              ['Context', lineage.context_sha256],
              ['Analysis', lineage.analysis_sha256],
              ['Output', lineage.output_sha256],
              ['Methodology', lineage.methodology_sha256],
            ] as const).map(([label, sha]) => (
              <div key={label} className="flex items-center gap-2">
                <dt className="w-24 shrink-0">{label}</dt>
                <dd className="font-mono truncate">{sha ?? '—'}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </ForecastPanel>
  )
}
