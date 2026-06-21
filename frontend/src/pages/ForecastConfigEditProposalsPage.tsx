/* eslint-disable @typescript-eslint/no-explicit-any */
/* Forecasting — Config Edit Proposals (Implementation Phase E).
 * An operator proposes an edit to a config item; the backend seeds from the current snapshot
 * (read-only), applies the edit in an isolated area, and returns a parity-proven report. Nothing is
 * written to the live data or database. forecast_controls is deprecated and not editable here. */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { EmptyState } from '../components/ui/EmptyState'
import { StatusPill } from './ForecastingPage'
import { api, getLocalUiRole } from '../lib/api'

const EDITABLE_DOMAINS = [
  { value: 'project', label: 'Project settings' },
  { value: 'forecast_model_controls', label: 'Model controls' },
  { value: 'forecast_staffing', label: 'Staffing mappings' },
  { value: 'owner_sov_crosswalk', label: 'Owner-SOV crosswalk' },
]

type Row = { key: string; value: string }

export function ForecastConfigEditProposalsPage() {
  const role = getLocalUiRole()
  const canEdit = role === 'operator' || role === 'admin'

  const { data: snapsResp } = useQuery({
    queryKey: ['forecast', 'config', 'snapshots'],
    queryFn: () => api.getForecastConfigSnapshots(),
  })
  const baseSnapshotId: string | undefined = snapsResp?.snapshots?.[0]?.snapshot_id

  const { data: editsResp, refetch } = useQuery({
    queryKey: ['forecast', 'config', 'edits'],
    queryFn: () => api.getForecastConfigEdits(),
  })

  const { data: runtimeResp } = useQuery({
    queryKey: ['forecast', 'runtime', 'status'],
    queryFn: () => api.getForecastRuntimeStatus(),
  })
  const promotionEnabled = Boolean(runtimeResp?.promotion?.enabled)

  const [promotingId, setPromotingId] = useState<string | null>(null)
  const [promoteResult, setPromoteResult] = useState<any | null>(null)
  const [promoteError, setPromoteError] = useState<string | null>(null)

  const [domain, setDomain] = useState('project')
  const [op, setOp] = useState<'modify' | 'add'>('modify')
  const [itemKey, setItemKey] = useState('')
  const [rows, setRows] = useState<Row[]>([{ key: '', value: '' }])
  const [submitting, setSubmitting] = useState(false)
  const [report, setReport] = useState<any | null>(null)
  const [error, setError] = useState<string | null>(null)

  function setRow(i: number, patch: Partial<Row>) {
    setRows((rs) => rs.map((r, idx) => (idx === i ? { ...r, ...patch } : r)))
  }

  async function onSubmit() {
    setSubmitting(true)
    setError(null)
    setReport(null)
    try {
      if (!baseSnapshotId) throw new Error('no_snapshot')
      const fields: Record<string, string> = {}
      for (const r of rows) {
        const k = r.key.trim()
        if (k) fields[k] = r.value
      }
      if (!itemKey.trim() || Object.keys(fields).length === 0) {
        setError('Enter an item key and at least one field.')
        return
      }
      const result = await api.proposeForecastConfigEdit({
        base_snapshot_id: baseSnapshotId,
        edits: [{ domain, op, item_key: itemKey.trim(), fields }],
      })
      setReport(result)
      await refetch()
    } catch (e: any) {
      const message = String(e?.message || '')
      setError(
        message.includes('forecast_config_edit_invalid_input')
          ? 'One or more edits are invalid for this domain.'
          : message.includes('forecast_config_snapshot_not_found')
            ? 'The base configuration snapshot could not be found.'
            : message.includes('forecast_config_edit_not_configured') || message.includes('503')
              ? 'Config editing is not available in this environment yet.'
              : 'The proposal could not be created.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  async function onPromote(editId: string) {
    if (!window.confirm('Promote this proposal to the live configuration? A backup is made first.')) {
      return
    }
    setPromotingId(editId)
    setPromoteError(null)
    setPromoteResult(null)
    try {
      const result = await api.promoteForecastConfigEdit(editId, true)
      setPromoteResult(result)
      await refetch()
    } catch (e: any) {
      const message = String(e?.message || '')
      setPromoteError(
        message.includes('forecast_config_promotion_disabled')
          ? 'Live promotion is turned off in this environment.'
          : message.includes('forecast_config_promotion_not_eligible')
            ? 'This proposal is not eligible (it must pass the parity check).'
            : message.includes('forecast_config_promotion_edit_not_found')
              ? 'That proposal could not be found.'
              : 'The promotion could not be completed.',
      )
    } finally {
      setPromotingId(null)
    }
  }

  const edits: any[] = Array.isArray(editsResp?.edits) ? editsResp.edits : []

  return (
    <div>
      <div className="text-xs mb-2">
        <Link to="/forecasting/config" className="underline">
          ← Back to forecast configuration
        </Link>
      </div>

      {canEdit && (
        <div className="card">
          <div className="section-title">Propose a configuration edit</div>
          <p className="text-sm text-[var(--hb-muted)]">
            Edits are validated and parity-checked in an isolated area. The live configuration is
            never changed. <span className="text-[var(--hb-muted)]">Model controls supersede the
            deprecated forecast controls.</span>
          </p>
          <div className="grid gap-3 mt-3">
            <label className="text-sm">
              <span className="block mb-1">Configuration area</span>
              <select
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                className="w-full rounded border border-[var(--hb-border)] bg-transparent px-2 py-1 text-sm"
              >
                {EDITABLE_DOMAINS.map((d) => (
                  <option key={d.value} value={d.value}>
                    {d.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="block mb-1">Change type</span>
              <select
                value={op}
                onChange={(e) => setOp(e.target.value as 'modify' | 'add')}
                disabled={domain === 'project'}
                className="w-full rounded border border-[var(--hb-border)] bg-transparent px-2 py-1 text-sm disabled:opacity-50"
              >
                <option value="modify">Modify existing</option>
                <option value="add">Add new</option>
              </select>
            </label>
            <label className="text-sm">
              <span className="block mb-1">Item key</span>
              <input
                type="text"
                value={itemKey}
                onChange={(e) => setItemKey(e.target.value)}
                className="w-full rounded border border-[var(--hb-border)] bg-transparent px-2 py-1 text-sm"
                placeholder="e.g. the control id, crosswalk id, or project key"
              />
            </label>
            <div className="text-sm">
              <span className="block mb-1">Fields</span>
              {rows.map((r, i) => (
                <div key={i} className="flex gap-2 mb-2">
                  <input
                    type="text"
                    value={r.key}
                    onChange={(e) => setRow(i, { key: e.target.value })}
                    className="flex-1 rounded border border-[var(--hb-border)] bg-transparent px-2 py-1 text-sm"
                    placeholder="field name"
                  />
                  <input
                    type="text"
                    value={r.value}
                    onChange={(e) => setRow(i, { value: e.target.value })}
                    className="flex-1 rounded border border-[var(--hb-border)] bg-transparent px-2 py-1 text-sm"
                    placeholder="value (money as text, e.g. 25000.00)"
                  />
                </div>
              ))}
              <button
                type="button"
                onClick={() => setRows((rs) => [...rs, { key: '', value: '' }])}
                className="text-xs underline text-[var(--hb-muted)]"
              >
                + Add field
              </button>
            </div>
          </div>
          <div className="flex items-center gap-3 mt-3">
            <button
              type="button"
              onClick={onSubmit}
              disabled={submitting || !baseSnapshotId}
              className="rounded border border-[var(--hb-accent)] px-3 py-1.5 text-sm disabled:opacity-50"
            >
              {submitting ? 'Checking…' : 'Propose edit'}
            </button>
            {error && <span className="text-sm text-rose-300">{error}</span>}
          </div>
        </div>
      )}

      {report && (
        <div className="card mt-3">
          <div className="flex items-center justify-between gap-3">
            <div className="section-title">Proposal result</div>
            <StatusPill status={report.parity?.status === 'pass' ? 'validated' : 'attention'} />
          </div>
          {report.status === 'succeeded' ? (
            <div className="text-sm">
              <p>
                Parity check: <span className="font-medium">{report.parity?.status}</span>
                {` · ${report.snapshot_item_count} settings in the proposed snapshot`}
              </p>
              {Array.isArray(report.changed_items) && report.changed_items.length > 0 && (
                <ul className="mt-2 list-disc pl-5 text-[var(--hb-muted)]">
                  {report.changed_items.map((c: any, i: number) => (
                    <li key={i}>
                      {c.domain} · {c.item_key} · {c.op} · {(c.changed_fields || []).join(', ')}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ) : (
            <p className="text-sm text-rose-300">{report.message || 'The proposal did not complete.'}</p>
          )}
        </div>
      )}

      <div className="card mt-3">
        <div className="section-title">Proposals</div>
        {edits.length === 0 ? (
          <EmptyState title="No proposals yet" hint="Propose a configuration edit to see it here." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-left text-[var(--hb-muted)] border-b border-[var(--hb-border)]">
                  <th className="py-2 pr-3">Proposal</th>
                  <th className="py-2 pr-3">Created</th>
                  <th className="py-2 pr-3">Parity</th>
                  <th className="py-2 pr-3">Changes</th>
                  <th className="py-2 pr-3">Live config</th>
                </tr>
              </thead>
              <tbody>
                {edits.map((e: any) => (
                  <tr key={e.edit_id} className="border-b border-[var(--hb-border)]">
                    <td className="py-2 pr-3">{e.edit_id}</td>
                    <td className="py-2 pr-3 text-[var(--hb-muted)]">{e.created_display || '—'}</td>
                    <td className="py-2 pr-3">
                      <StatusPill status={e.parity_status === 'pass' ? 'validated' : 'attention'} />
                    </td>
                    <td className="py-2 pr-3 text-[var(--hb-muted)]">{e.changed_count ?? 0}</td>
                    <td className="py-2 pr-3">
                      {canEdit && promotionEnabled && e.parity_status === 'pass' && e.status === 'succeeded' ? (
                        <button
                          type="button"
                          onClick={() => onPromote(e.edit_id)}
                          disabled={promotingId === e.edit_id}
                          className="rounded border border-[var(--hb-accent)] px-2 py-1 text-xs disabled:opacity-50"
                        >
                          {promotingId === e.edit_id ? 'Promoting…' : 'Promote to live'}
                        </button>
                      ) : (
                        <span className="text-xs text-[var(--hb-muted)]">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!promotionEnabled && (
          <p className="text-xs text-[var(--hb-muted)] mt-2">
            Live promotion is turned off in this environment.
          </p>
        )}
        <p className="text-xs text-[var(--hb-muted)] mt-1">
          Promoting updates the recorded current configuration (the system-of-record shown in the
          viewer). It does not change how forecasts are generated.
        </p>
        {promoteResult && (
          <div className="mt-2 text-sm">
            <StatusPill status={promoteResult.status === 'promoted' ? 'validated' : 'attention'} />{' '}
            <span className="ml-1">
              {promoteResult.status === 'promoted'
                ? 'Promoted to live configuration.'
                : 'Promotion did not certify.'}
            </span>
            {promoteResult.backup_created && (
              <span className="text-emerald-300 ml-2">A backup of the live configuration was made.</span>
            )}
          </div>
        )}
        {promoteError && <p className="text-sm text-rose-300 mt-2">{promoteError}</p>}
      </div>
    </div>
  )
}
