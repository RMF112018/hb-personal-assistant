/* Operator assumptions capture (first interactive forecast write surface).
 * Operator-entered assumptions persist directly into the v66 managed-DB tables via role-guarded
 * POST/PATCH. Operators create/edit operator assumptions and create/mark-satisfied required
 * assumptions; lists refetch after each write. Read paths never surface raw_json/run_id. */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ClipboardList } from 'lucide-react'

import { EmptyState } from '../ui/EmptyState'
import { api } from '../../lib/api'
import {
  ForecastAdvisoryStrip,
  ForecastPanel,
  ForecastTable,
  ForecastTd,
  ForecastTh,
} from './ForecastPrimitives'
import { ForecastStatusPill } from './ForecastStatusPill'

const CONFIDENCE_IMPACTS = ['', 'raises', 'lowers', 'neutral']
const INPUT_CLASS =
  'w-full rounded border border-[var(--hb-border)] bg-transparent px-2 py-1 text-sm'
const BTN_CLASS =
  'rounded border border-[var(--hb-accent)] px-3 py-1.5 text-sm disabled:opacity-50'

function describeError(e: unknown): string {
  const message = e instanceof Error ? e.message : ''
  if (message.includes('operator_role_required')) return 'Operator access is required to save.'
  if (message.includes('not_available')) return 'Forecast database is not available.'
  return 'Could not save. Please try again.'
}

export function ForecastOperatorAssumptionsPanel({ project }: { project: string }) {
  const { data: opData, error: opError, refetch: refetchOps } = useQuery({
    queryKey: ['forecast', 'operator-assumptions', project],
    queryFn: () => api.getForecastOperatorAssumptions(project),
  })
  const { data: reqData, refetch: refetchReq } = useQuery({
    queryKey: ['forecast', 'required-assumptions', project],
    queryFn: () => api.getForecastRequiredAssumptions(project),
  })
  const assumptions = opData?.assumptions ?? []
  const required = reqData?.required ?? []

  // create-operator-assumption form
  const [assumptionType, setAssumptionType] = useState('')
  const [value, setValue] = useState('')
  const [unit, setUnit] = useState('')
  const [budgetCodeKey, setBudgetCodeKey] = useState('')
  const [confidenceImpact, setConfidenceImpact] = useState('')
  const [isRequired, setIsRequired] = useState(false)
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  // declare-required form
  const [reqType, setReqType] = useState('')
  const [reqReason, setReqReason] = useState('')
  const [reqSaving, setReqSaving] = useState(false)
  const [reqError, setReqError] = useState<string | null>(null)

  // inline edit
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')

  async function onAddAssumption() {
    if (!assumptionType.trim()) {
      setSaveError('Assumption type is required.')
      return
    }
    setSaving(true)
    setSaveError(null)
    try {
      await api.createForecastOperatorAssumption(project, {
        assumption_type: assumptionType.trim(),
        value: value.trim() || undefined,
        unit: unit.trim() || undefined,
        budget_code_key: budgetCodeKey.trim() || undefined,
        confidence_impact: confidenceImpact || undefined,
        is_required: isRequired,
        notes: notes.trim() || undefined,
      })
      setAssumptionType('')
      setValue('')
      setUnit('')
      setBudgetCodeKey('')
      setConfidenceImpact('')
      setIsRequired(false)
      setNotes('')
      await refetchOps()
    } catch (e: unknown) {
      setSaveError(describeError(e))
    } finally {
      setSaving(false)
    }
  }

  async function onSaveEdit(assumptionId: string) {
    try {
      await api.editForecastOperatorAssumption(assumptionId, { value: editValue.trim() || undefined })
      setEditingId(null)
      setEditValue('')
      await refetchOps()
    } catch (e: unknown) {
      setSaveError(describeError(e))
    }
  }

  async function onAddRequired() {
    if (!reqType.trim()) {
      setReqError('Assumption type is required.')
      return
    }
    setReqSaving(true)
    setReqError(null)
    try {
      await api.createForecastRequiredAssumption(project, {
        assumption_type: reqType.trim(),
        reason: reqReason.trim() || undefined,
      })
      setReqType('')
      setReqReason('')
      await refetchReq()
    } catch (e: unknown) {
      setReqError(describeError(e))
    } finally {
      setReqSaving(false)
    }
  }

  async function onToggleSatisfied(id: string, next: boolean) {
    try {
      await api.setForecastRequiredAssumptionSatisfied(id, next)
      await refetchReq()
    } catch (e: unknown) {
      setReqError(describeError(e))
    }
  }

  return (
    <ForecastPanel
      icon={ClipboardList}
      title="Operator assumptions"
      description="Capture the operator-supplied assumptions and required inputs that feed the forecast."
    >
      {opError && (
        <ForecastAdvisoryStrip>
          Forecast database not available. Assumptions can be captured once it is configured.
        </ForecastAdvisoryStrip>
      )}

      {/* Capture form */}
      <div className="grid gap-3 sm:grid-cols-2 mt-2">
        <label className="text-sm">
          <span className="block mb-1">Assumption type</span>
          <input
            type="text"
            aria-label="Assumption type"
            value={assumptionType}
            onChange={(e) => setAssumptionType(e.target.value)}
            className={INPUT_CLASS}
            placeholder="e.g. labor_rate"
          />
        </label>
        <label className="text-sm">
          <span className="block mb-1">Value</span>
          <input
            type="text"
            aria-label="Value"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            className={INPUT_CLASS}
            placeholder="e.g. 125.00"
          />
        </label>
        <label className="text-sm">
          <span className="block mb-1">Unit</span>
          <input
            type="text"
            aria-label="Unit"
            value={unit}
            onChange={(e) => setUnit(e.target.value)}
            className={INPUT_CLASS}
            placeholder="e.g. usd_per_hour"
          />
        </label>
        <label className="text-sm">
          <span className="block mb-1">Budget code</span>
          <input
            type="text"
            aria-label="Budget code"
            value={budgetCodeKey}
            onChange={(e) => setBudgetCodeKey(e.target.value)}
            className={INPUT_CLASS}
            placeholder="optional"
          />
        </label>
        <label className="text-sm">
          <span className="block mb-1">Confidence impact</span>
          <select
            aria-label="Confidence impact"
            value={confidenceImpact}
            onChange={(e) => setConfidenceImpact(e.target.value)}
            className={INPUT_CLASS}
          >
            {CONFIDENCE_IMPACTS.map((c) => (
              <option key={c || 'none'} value={c}>
                {c || '—'}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="block mb-1">Notes</span>
          <input
            type="text"
            aria-label="Notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className={INPUT_CLASS}
            placeholder="optional"
          />
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-3 mt-3">
        <label className="text-sm flex items-center gap-2">
          <input
            type="checkbox"
            checked={isRequired}
            onChange={(e) => setIsRequired(e.target.checked)}
          />
          Mark required
        </label>
        <button type="button" onClick={onAddAssumption} disabled={saving} className={BTN_CLASS}>
          {saving ? 'Saving…' : 'Add assumption'}
        </button>
        {saveError && <span className="text-sm text-rose-300">{saveError}</span>}
      </div>

      {/* Operator assumptions table */}
      <div className="mt-4">
        <h3 className="forecast-eyebrow mb-2">Captured assumptions · {assumptions.length}</h3>
        {assumptions.length === 0 ? (
          <EmptyState
            title="No operator assumptions yet"
            hint="Add an assumption above to capture it in the forecast database."
          />
        ) : (
          <ForecastTable
            headers={
              <>
                <ForecastTh>Type</ForecastTh>
                <ForecastTh>Value</ForecastTh>
                <ForecastTh>Unit</ForecastTh>
                <ForecastTh>Impact</ForecastTh>
                <ForecastTh>State</ForecastTh>
                <ForecastTh></ForecastTh>
              </>
            }
          >
            {assumptions.map((a) => (
              <tr key={a.assumption_id}>
                <ForecastTd>{a.assumption_type}</ForecastTd>
                <ForecastTd className="tabular-nums">
                  {editingId === a.assumption_id ? (
                    <input
                      type="text"
                      aria-label={`Edit value ${a.assumption_id}`}
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      className={INPUT_CLASS}
                    />
                  ) : (
                    a.value ?? '—'
                  )}
                </ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">{a.unit ?? '—'}</ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">
                  {a.confidence_impact ?? '—'}
                </ForecastTd>
                <ForecastTd>
                  {a.overridden ? (
                    <ForecastStatusPill status="attention" />
                  ) : (
                    <ForecastStatusPill status="validated" />
                  )}
                </ForecastTd>
                <ForecastTd>
                  {editingId === a.assumption_id ? (
                    <button
                      type="button"
                      onClick={() => onSaveEdit(a.assumption_id)}
                      className="text-sm text-[var(--hb-accent)]"
                    >
                      Save
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => {
                        setEditingId(a.assumption_id)
                        setEditValue(a.value ?? '')
                      }}
                      className="text-sm text-[var(--hb-accent)]"
                    >
                      Edit
                    </button>
                  )}
                </ForecastTd>
              </tr>
            ))}
          </ForecastTable>
        )}
      </div>

      {/* Required assumptions */}
      <div className="mt-6">
        <h3 className="forecast-eyebrow mb-2">Required assumptions · {required.length}</h3>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-sm">
            <span className="block mb-1">Required type</span>
            <input
              type="text"
              aria-label="Required type"
              value={reqType}
              onChange={(e) => setReqType(e.target.value)}
              className={INPUT_CLASS}
              placeholder="e.g. escalation_rate"
            />
          </label>
          <label className="text-sm">
            <span className="block mb-1">Reason</span>
            <input
              type="text"
              aria-label="Reason"
              value={reqReason}
              onChange={(e) => setReqReason(e.target.value)}
              className={INPUT_CLASS}
              placeholder="optional"
            />
          </label>
        </div>
        <div className="flex flex-wrap items-center gap-3 mt-3">
          <button type="button" onClick={onAddRequired} disabled={reqSaving} className={BTN_CLASS}>
            {reqSaving ? 'Saving…' : 'Declare required'}
          </button>
          {reqError && <span className="text-sm text-rose-300">{reqError}</span>}
        </div>

        {required.length > 0 && (
          <div className="mt-3">
            <ForecastTable
              headers={
                <>
                  <ForecastTh>Type</ForecastTh>
                  <ForecastTh>Reason</ForecastTh>
                  <ForecastTh>Status</ForecastTh>
                  <ForecastTh></ForecastTh>
                </>
              }
            >
              {required.map((r) => (
                <tr key={r.id}>
                  <ForecastTd>{r.assumption_type}</ForecastTd>
                  <ForecastTd className="text-[var(--hb-muted)]">{r.reason ?? '—'}</ForecastTd>
                  <ForecastTd>
                    <ForecastStatusPill status={r.satisfied ? 'validated' : 'attention'} />
                  </ForecastTd>
                  <ForecastTd>
                    <button
                      type="button"
                      onClick={() => onToggleSatisfied(r.id, !r.satisfied)}
                      className="text-sm text-[var(--hb-accent)]"
                    >
                      {r.satisfied ? 'Mark unsatisfied' : 'Mark satisfied'}
                    </button>
                  </ForecastTd>
                </tr>
              ))}
            </ForecastTable>
          </div>
        )}
      </div>
    </ForecastPanel>
  )
}
