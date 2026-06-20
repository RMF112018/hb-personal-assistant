/* eslint-disable @typescript-eslint/no-explicit-any */
/* Forecasting — External-Forecast Evaluation (Implementation Phase 4).
 * Lets an operator upload an external/operator forecast (Excel/CSV), map its columns, and compare
 * it against actuals / budget / ERP-JTD / the backend model / prior external forecasts. The
 * evaluation writes only to an isolated work area; it never changes the live data or database and
 * never calls an LLM. Business labels only — no paths, run stamps, or internals are shown. */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { EmptyState } from '../components/ui/EmptyState'
import { StatusPill } from './ForecastingPage'
import { api } from '../lib/api'

const ROLE_FIELDS: { key: string; label: string }[] = [
  { key: 'budget_code', label: 'Budget code' },
  { key: 'month', label: 'Month' },
  { key: 'value', label: 'Value' },
  { key: 'eac', label: 'EAC' },
  { key: 'remaining', label: 'Remaining' },
]

const SOURCE_SYSTEMS = ['excel', 'procore', 'sage', 'manual', 'other']

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
  const [preview, setPreview] = useState<any | null>(null)
  const [roles, setRoles] = useState<Record<string, string>>({})
  const [result, setResult] = useState<any | null>(null)

  const { data: listResp, refetch } = useQuery({
    queryKey: ['forecast', 'external', 'evaluations'],
    queryFn: () => api.getExternalEvaluations(),
  })
  const evaluations: any[] = Array.isArray(listResp?.evaluations) ? listResp.evaluations : []

  function friendlyError(e: any): string {
    const s = e?.status
    if (s === 503) return 'External-forecast evaluation is not configured in this environment yet.'
    if (s === 403) return 'You need the operator role to upload and evaluate forecasts.'
    if (s === 400) return 'The uploaded file could not be read. Please upload a .xlsx or .csv file.'
    return 'The request could not be completed.'
  }

  async function onUpload(file: File) {
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const b64 = await readFileAsBase64(file)
      const prev = await api.previewExternalForecast(file.name, b64, sourceSystem, period || null)
      setPreview(prev)
      const mapping = await api.proposeExternalMapping(prev.import_id)
      setRoles({ ...(mapping.proposed_column_roles || {}) })
    } catch (e: any) {
      setError(friendlyError(e))
    } finally {
      setBusy(false)
    }
  }

  async function onEvaluate() {
    if (!preview) return
    setBusy(true)
    setError(null)
    try {
      const res = await api.evaluateExternalForecast(preview.import_id, roles)
      setResult(res)
      await refetch()
    } catch (e: any) {
      setError(friendlyError(e))
    } finally {
      setBusy(false)
    }
  }

  const columns: string[] = Array.isArray(preview?.columns) ? preview.columns : []

  return (
    <div>
      <div className="text-xs mb-2">
        <Link to="/forecasting" className="underline">
          ← Back to forecast packages
        </Link>
      </div>

      {/* Step 1 — upload */}
      <div className="card">
        <div className="section-title">Upload an external forecast</div>
        <p className="text-sm text-[var(--hb-muted)]">
          Compare an external or operator-supplied forecast against actuals, the current budget, ERP
          job-to-date, the backend model, and prior external forecasts. The evaluation writes only to
          an isolated work area — the live project data and database are never changed.
        </p>
        <div className="flex flex-wrap items-center gap-3 mt-3">
          <label className="text-sm">
            Source:{' '}
            <select
              value={sourceSystem}
              onChange={(e) => setSourceSystem(e.target.value)}
              className="bg-transparent border border-[var(--hb-border)] rounded px-2 py-1"
            >
              {SOURCE_SYSTEMS.map((s) => (
                <option key={s} value={s}>
                  {s}
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
        {error && <p className="text-sm text-rose-300 mt-2">{error}</p>}
      </div>

      {/* Step 2 — map columns */}
      {preview && (
        <div className="card mt-3">
          <div className="section-title">Map columns</div>
          <p className="text-sm text-[var(--hb-muted)]">
            {preview.display_label} · {preview.row_count} rows
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
          <button
            type="button"
            onClick={onEvaluate}
            disabled={busy || !roles.budget_code || !(roles.value || roles.eac)}
            className="mt-3 rounded border border-[var(--hb-accent)] px-3 py-1.5 text-sm disabled:opacity-50"
          >
            {busy ? 'Evaluating…' : 'Evaluate forecast'}
          </button>
        </div>
      )}

      {/* Step 3 — results */}
      {result && result.status === 'succeeded' && (
        <ResultsView result={result} />
      )}
      {result && result.status === 'failed' && (
        <div className="card mt-3">
          <EmptyState title="Evaluation failed" hint={result.message || 'Please try again.'} />
        </div>
      )}

      {/* History */}
      <div className="card mt-3">
        <div className="section-title">Prior evaluations</div>
        {evaluations.length === 0 ? (
          <EmptyState title="No evaluations yet" hint="Upload a forecast to see it here." />
        ) : (
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="text-left text-[var(--hb-muted)] border-b border-[var(--hb-border)]">
                <th className="py-2 pr-3">Evaluation</th>
                <th className="py-2 pr-3">Status</th>
                <th className="py-2 pr-3">Generated</th>
              </tr>
            </thead>
            <tbody>
              {evaluations.map((e: any) => (
                <tr key={e.eval_id} className="border-b border-[var(--hb-border)]">
                  <td className="py-2 pr-3">{e.display_label}</td>
                  <td className="py-2 pr-3">
                    <StatusPill status={e.status === 'succeeded' ? 'validated' : 'attention'} />
                  </td>
                  <td className="py-2 pr-3 text-[var(--hb-muted)]">{e.generated_display || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

function ResultsView({ result }: { result: any }) {
  const accuracy: any[] = Array.isArray(result.accuracy) ? result.accuracy : []
  const anomalies: any[] = Array.isArray(result.anomalies) ? result.anomalies : []
  const reviewItems: any[] = Array.isArray(result.review_items) ? result.review_items : []
  const baselines: string[] = Array.isArray(result.baselines_compared) ? result.baselines_compared : []
  return (
    <div className="card mt-3">
      <div className="section-title">{result.display_label || 'Evaluation'}</div>
      <p className="text-sm">
        Mapped {result.mapped_count} rows · {result.unmapped_count} unmapped · baselines:{' '}
        {baselines.join(', ') || 'none'}
      </p>
      <p className="text-xs text-emerald-300 mt-1">
        No changes were made to the live project data or database.
      </p>

      {accuracy.length > 0 && (
        <div className="mt-3">
          <div className="text-sm font-medium mb-1">Accuracy</div>
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="text-left text-[var(--hb-muted)] border-b border-[var(--hb-border)]">
                <th className="py-1 pr-3">Baseline</th>
                <th className="py-1 pr-3">Metric</th>
                <th className="py-1 pr-3">Value</th>
                <th className="py-1 pr-3">N</th>
              </tr>
            </thead>
            <tbody>
              {accuracy.map((a: any, i: number) => (
                <tr key={i} className="border-b border-[var(--hb-border)]">
                  <td className="py-1 pr-3">{a.baseline_label}</td>
                  <td className="py-1 pr-3 uppercase">{a.metric}</td>
                  <td className="py-1 pr-3">{a.metric_value}</td>
                  <td className="py-1 pr-3 text-[var(--hb-muted)]">{a.sample_n}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {anomalies.length > 0 && (
        <div className="mt-3">
          <div className="text-sm font-medium mb-1">Anomalies ({anomalies.length})</div>
          <ul className="text-sm list-disc pl-5">
            {anomalies.map((a: any, i: number) => (
              <li key={i}>
                <span className="uppercase text-xs text-[var(--hb-muted)]">{a.severity}</span> ·{' '}
                {a.message}
                {a.budget_code_key ? ` (${a.budget_code_key})` : ''}
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
    </div>
  )
}
