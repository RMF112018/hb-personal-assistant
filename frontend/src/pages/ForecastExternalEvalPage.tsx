/* External forecast evaluation — guided compare flow (read-only toward live systems). */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import {
  ForecastActionButton,
  ForecastActionLink,
  ForecastBackLink,
  ForecastPageHeader,
  ForecastShell,
  ForecastSubnav,
  ForecastTable,
  ForecastTd,
  ForecastTh,
  ForecastWizardRail,
} from '../components/forecast/ForecastPageChrome'
import { ForecastStatusPill } from '../components/forecast/ForecastStatusPill'
import { EmptyState } from '../components/ui/EmptyState'
import { api } from '../lib/api'

const ROLE_FIELDS: { key: string; label: string }[] = [
  { key: 'budget_code', label: 'Budget code' },
  { key: 'month', label: 'Month' },
  { key: 'value', label: 'Forecast value' },
  { key: 'eac', label: 'Estimate at completion' },
  { key: 'remaining', label: 'Remaining' },
]

const SOURCE_LABELS: Record<string, string> = {
  excel: 'Excel workbook',
  procore: 'Procore export',
  sage: 'Sage export',
  manual: 'Manual entry',
  other: 'Other',
}

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = String(reader.result || '')
      const comma = result.indexOf(',')
      resolve(comma >= 0 ? result.slice(comma + 1) : result)
    }
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

export function ForecastExternalEvalPage() {
  const [sourceSystem, setSourceSystem] = useState('excel')
  const [period, setPeriod] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [unconfigured, setUnconfigured] = useState(false)
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null)
  const [roles, setRoles] = useState<Record<string, string>>({})
  const [result, setResult] = useState<Record<string, unknown> | null>(null)

  const { data: listResp, refetch } = useQuery({
    queryKey: ['forecast', 'external', 'evaluations'],
    queryFn: () => api.getExternalEvaluations(),
  })
  const evaluations = Array.isArray(listResp?.evaluations) ? listResp.evaluations : []

  function friendlyError(e: unknown): string {
    const s = (e as { status?: number })?.status
    if (s === 503) return 'External forecast evaluation is not ready yet. Check storage settings.'
    if (s === 403) return 'You need the operator role to upload and evaluate forecasts.'
    if (s === 400) return 'The uploaded file could not be read. Please upload a .xlsx or .csv file.'
    return 'The request could not be completed.'
  }

  async function onUpload(file: File) {
    setBusy(true)
    setError(null)
    setUnconfigured(false)
    setResult(null)
    try {
      const b64 = await readFileAsBase64(file)
      const prev = (await api.previewExternalForecast(
        file.name,
        b64,
        sourceSystem,
        period || null,
      )) as Record<string, unknown>
      setPreview(prev)
      const mapping = (await api.proposeExternalMapping(prev.import_id as string)) as Record<string, unknown>
      setRoles({ ...((mapping.proposed_column_roles as Record<string, string>) || {}) })
    } catch (e: unknown) {
      setUnconfigured((e as { status?: number })?.status === 503)
      setError(friendlyError(e))
    } finally {
      setBusy(false)
    }
  }

  async function onEvaluate() {
    if (!preview) return
    setBusy(true)
    setError(null)
    setUnconfigured(false)
    try {
      const res = (await api.evaluateExternalForecast(preview.import_id as string, roles)) as Record<
        string,
        unknown
      >
      setResult(res)
      await refetch()
    } catch (e: unknown) {
      setUnconfigured((e as { status?: number })?.status === 503)
      setError(friendlyError(e))
    } finally {
      setBusy(false)
    }
  }

  const columns: string[] = Array.isArray(preview?.columns) ? preview.columns : []
  const wizardSteps: { label: string; state: 'pending' | 'active' | 'done' }[] = [
    { label: 'Upload', state: preview ? 'done' : 'active' },
    { label: 'Map columns', state: preview ? (result ? 'done' : 'active') : 'pending' },
    { label: 'Review findings', state: result ? 'active' : 'pending' },
  ]

  return (
    <ForecastShell>
      <ForecastBackLink />
      <ForecastSubnav />

      <section className="forecast-panel">
        <ForecastPageHeader
          title="Evaluate external forecast"
          subtitle="Compare an operator forecast against actuals, budget, job-to-date, the HB model, and prior evaluations. Advisory only — live systems are never changed."
        />
        <ForecastWizardRail steps={wizardSteps} />
      </section>

      <section className="forecast-panel">
        <h2 className="forecast-section-label">Upload operator forecast</h2>
        <div className="flex flex-wrap items-center gap-3 mt-3">
          <label className="text-sm">
            Source:{' '}
            <select
              value={sourceSystem}
              onChange={(e) => setSourceSystem(e.target.value)}
              className="bg-transparent border border-[var(--hb-border)] rounded px-2 py-1"
            >
              {Object.entries(SOURCE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            Period:{' '}
            <input
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              placeholder="2026-06"
              className="bg-transparent border border-[var(--hb-border)] rounded px-2 py-1"
            />
          </label>
          <input
            type="file"
            accept=".xlsx,.csv"
            disabled={busy}
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) void onUpload(f)
            }}
            className="text-sm"
          />
        </div>
        {error && (
          <p className="text-sm text-rose-300 mt-2">
            {error}
            {unconfigured && (
              <>
                {' '}
                <ForecastActionLink to="/forecasting/runtime">Open storage settings</ForecastActionLink>
              </>
            )}
          </p>
        )}
      </section>

      {preview && (
        <section className="forecast-panel">
          <h2 className="forecast-section-label">Map columns</h2>
          <p className="text-sm text-[var(--hb-muted)]">
            {String(preview.display_label || 'Upload')} · {String(preview.row_count ?? 0)} rows
          </p>
          <div className="flex flex-wrap gap-4 mt-3">
            {ROLE_FIELDS.map((f) => (
              <label key={f.key} className="text-sm">
                {f.label}:{' '}
                <select
                  value={roles[f.key] || ''}
                  onChange={(e) => setRoles({ ...roles, [f.key]: e.target.value })}
                  className="bg-transparent border border-[var(--hb-border)] rounded px-2 py-1"
                >
                  <option value="">—</option>
                  {columns.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </div>
          <div className="mt-3">
            <ForecastActionButton
              onClick={onEvaluate}
              disabled={busy || !roles.budget_code || !(roles.value || roles.eac)}
            >
              {busy ? 'Evaluating…' : 'Run evaluation'}
            </ForecastActionButton>
          </div>
        </section>
      )}

      {/* Step 3 — results */}
      {result && result.status === 'succeeded' && <ResultsView result={result} />}
      {result && result.status === 'failed' && (
        <section className="forecast-panel">
          <EmptyState
            title="Evaluation failed"
            hint={String(result.message || 'Please try again.')}
          />
        </section>
      )}

      <section className="forecast-panel">
        <h2 className="forecast-section-label">Prior evaluations</h2>
        {evaluations.length === 0 ? (
          <EmptyState title="No evaluations yet" hint="Upload a forecast to see it here." />
        ) : (
          <ForecastTable
            headers={
              <>
                <ForecastTh>Evaluation</ForecastTh>
                <ForecastTh>Status</ForecastTh>
                <ForecastTh>Generated</ForecastTh>
              </>
            }
          >
            {evaluations.map((e: Record<string, unknown>) => (
              <tr key={String(e.eval_id)}>
                <ForecastTd>{String(e.display_label || 'Evaluation')}</ForecastTd>
                <ForecastTd>
                  <ForecastStatusPill status={e.status === 'succeeded' ? 'validated' : 'attention'} />
                </ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">{String(e.generated_display || '—')}</ForecastTd>
              </tr>
            ))}
          </ForecastTable>
        )}
      </section>
    </ForecastShell>
  )
}

function ResultsView({ result }: { result: Record<string, unknown> }) {
  const accuracy = Array.isArray(result.accuracy) ? result.accuracy : []
  const anomalies = Array.isArray(result.anomalies) ? result.anomalies : []
  const reviewItems = Array.isArray(result.review_items) ? result.review_items : []
  const baselines: string[] = Array.isArray(result.baselines_compared) ? result.baselines_compared : []
  return (
    <section className="forecast-panel">
      <h2 className="forecast-section-label">{String(result.display_label || 'Evaluation results')}</h2>
      <p className="text-sm">
        Mapped {String(result.mapped_count ?? 0)} rows · {String(result.unmapped_count ?? 0)} unmapped
        · Compared to: {baselines.join(', ') || 'none'}
      </p>
      <p className="text-xs text-emerald-300 mt-1">
        No changes were made to the live project data or database.
      </p>

      {accuracy.length > 0 && (
        <div className="mt-3">
          <div className="text-sm font-medium mb-1">Variance & accuracy (advisory)</div>
          <ForecastTable
            headers={
              <>
                <ForecastTh>Baseline</ForecastTh>
                <ForecastTh>Metric</ForecastTh>
                <ForecastTh>Value</ForecastTh>
                <ForecastTh>N</ForecastTh>
              </>
            }
          >
            {accuracy.map((a: Record<string, unknown>, i: number) => (
              <tr key={i}>
                <ForecastTd>{String(a.baseline_label || '—')}</ForecastTd>
                <ForecastTd className="uppercase">{String(a.metric || '—')}</ForecastTd>
                <ForecastTd>{String(a.metric_value ?? '—')}</ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">{String(a.sample_n ?? '—')}</ForecastTd>
              </tr>
            ))}
          </ForecastTable>
        </div>
      )}

      {anomalies.length > 0 && (
        <div className="mt-3">
          <div className="text-sm font-medium mb-1">Anomalies ({anomalies.length})</div>
          <ul className="text-sm list-disc pl-5">
            {anomalies.map((a: Record<string, unknown>, i: number) => (
              <li key={i}>
                <span className="uppercase text-xs text-[var(--hb-muted)]">{String(a.severity || '')}</span>{' '}
                · {String(a.message || '')}
                {a.budget_code_key ? ` (${String(a.budget_code_key)})` : ''}
              </li>
            ))}
          </ul>
        </div>
      )}

      {reviewItems.length > 0 && (
        <p className="text-sm text-amber-300 mt-3">
          {reviewItems.length} item{reviewItems.length === 1 ? '' : 's'} flagged for human review.
        </p>
      )}
    </section>
  )
}
