import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../../lib/api'
import type { StaffingConfigRow } from '../../lib/api'
import { SectionCard } from '../common/SectionCard'
import { BTN_CLASS, INPUT_CLASS, canEditStaffing, describeStaffingError, humanizeCode } from './staffingShared'

const EMPLOYMENT_TYPES = ['Hourly', 'Part Time', 'Full Time', 'Intern']
const RATE_UNITS = ['hourly', 'daily', 'weekly']

type Draft = {
  role_title: string
  person_name: string
  employment_type: string
  cost_code: string
  rate_unit: string
  start_date: string
  finish_date: string
  lab_rate: string
  lbn_rate: string
  mat_rate: string
}

const EMPTY_DRAFT: Draft = {
  role_title: '', person_name: '', employment_type: 'Full Time', cost_code: '', rate_unit: 'weekly',
  start_date: '', finish_date: '', lab_rate: '', lbn_rate: '', mat_rate: '',
}

function toDraft(row: StaffingConfigRow): Draft {
  return {
    role_title: row.role_title ?? '', person_name: row.person_name ?? '',
    employment_type: row.employment_type ?? 'Full Time', cost_code: row.cost_code ?? '',
    rate_unit: row.rate_unit ?? 'weekly', start_date: row.start_date ?? '',
    finish_date: row.finish_date ?? '', lab_rate: row.lab_rate ?? '',
    lbn_rate: row.lbn_rate ?? '', mat_rate: row.mat_rate ?? '',
  }
}

function DraftFields({ draft, onChange }: { draft: Draft; onChange: (d: Draft) => void }) {
  const set = (k: keyof Draft) => (v: string) => onChange({ ...draft, [k]: v })
  return (
    <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
      <input aria-label="Role/title" placeholder="Role/title" className={INPUT_CLASS}
        value={draft.role_title} onChange={(e) => set('role_title')(e.target.value)} />
      <input aria-label="Person" placeholder="Person (optional)" className={INPUT_CLASS}
        value={draft.person_name} onChange={(e) => set('person_name')(e.target.value)} />
      <select aria-label="Employment type" className={INPUT_CLASS} value={draft.employment_type}
        onChange={(e) => set('employment_type')(e.target.value)}>
        {EMPLOYMENT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
      </select>
      <input aria-label="Cost code" placeholder="Cost code" className={INPUT_CLASS}
        value={draft.cost_code} onChange={(e) => set('cost_code')(e.target.value)} />
      <select aria-label="Rate unit" className={INPUT_CLASS} value={draft.rate_unit}
        onChange={(e) => set('rate_unit')(e.target.value)}>
        {RATE_UNITS.map((u) => <option key={u} value={u}>{u}</option>)}
      </select>
      <input aria-label="Start date" type="date" className={INPUT_CLASS}
        value={draft.start_date} onChange={(e) => set('start_date')(e.target.value)} />
      <input aria-label="Finish date" type="date" className={INPUT_CLASS}
        value={draft.finish_date} onChange={(e) => set('finish_date')(e.target.value)} />
      <input aria-label="LAB rate" placeholder="LAB rate" className={INPUT_CLASS}
        value={draft.lab_rate} onChange={(e) => set('lab_rate')(e.target.value)} />
      <input aria-label="LBN rate" placeholder="LBN rate" className={INPUT_CLASS}
        value={draft.lbn_rate} onChange={(e) => set('lbn_rate')(e.target.value)} />
      <input aria-label="MAT rate" placeholder="MAT rate" className={INPUT_CLASS}
        value={draft.mat_rate} onChange={(e) => set('mat_rate')(e.target.value)} />
    </div>
  )
}

function RowErrors({ row }: { row: StaffingConfigRow }) {
  if (row.validation_status !== 'invalid' || !row.validation_errors_json?.length) return null
  return (
    <ul className="mt-1 list-disc pl-5 text-xs text-rose-300">
      {row.validation_errors_json.map((e, i) => (
        <li key={`${e.code}-${i}`}>{e.message || humanizeCode(e.code)}</li>
      ))}
    </ul>
  )
}

export function StaffingConfigGrid({ project }: { project: string }) {
  const queryClient = useQueryClient()
  const canEdit = canEditStaffing()
  const { data, isLoading, error } = useQuery({
    queryKey: ['staffing', 'config', project],
    queryFn: () => api.getProjectStaffingConfig(project),
  })

  const [addDraft, setAddDraft] = useState<Draft>(EMPTY_DRAFT)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editDraft, setEditDraft] = useState<Draft>(EMPTY_DRAFT)
  const [busy, setBusy] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  async function invalidate() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['staffing', 'config', project] }),
      queryClient.invalidateQueries({ queryKey: ['staffing', 'readiness', project] }),
    ])
  }

  async function run(fn: () => Promise<unknown>) {
    setBusy(true)
    setSaveError(null)
    try {
      await fn()
      await invalidate()
    } catch (e) {
      setSaveError(describeStaffingError(e))
    } finally {
      setBusy(false)
    }
  }

  const rows = data?.rows ?? []

  return (
    <SectionCard
      title="Staffing configuration"
      description="Project staffing assignments. Invalid rows stay visible with their issues."
    >
      {isLoading && <p className="text-sm text-[var(--hb-muted)]">Loading staffing rows…</p>}
      {error && <p className="text-sm text-rose-300">Staffing configuration is unavailable.</p>}

      {data && (
        <div className="space-y-3">
          {rows.length === 0 && (
            <p className="text-sm text-[var(--hb-muted)]">No staffing rows yet.</p>
          )}
          <ul className="space-y-2">
            {rows.map((row) => (
              <li key={row.staffing_config_id} className="rounded border border-[var(--hb-border)] p-2">
                {editingId === row.staffing_config_id ? (
                  <div className="space-y-2">
                    <DraftFields draft={editDraft} onChange={setEditDraft} />
                    <div className="flex gap-2">
                      <button type="button" className={BTN_CLASS} disabled={busy}
                        onClick={() => run(async () => {
                          await api.updateProjectStaffingConfig(project, row.staffing_config_id, { ...editDraft })
                          setEditingId(null)
                        })}>Save</button>
                      <button type="button" className={BTN_CLASS} disabled={busy}
                        onClick={() => setEditingId(null)}>Cancel</button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 text-sm">
                      <div className="font-medium">
                        {row.role_title || 'Untitled role'}
                        {row.person_name ? ` — ${row.person_name}` : ' — TBD'}
                      </div>
                      <div className="text-xs text-[var(--hb-muted)]">
                        {row.cost_code} · {row.employment_type} · {row.rate_unit} ·{' '}
                        {row.start_date} → {row.finish_date}
                        {row.validation_status === 'invalid' ? ' · Needs attention' : ''}
                      </div>
                      <RowErrors row={row} />
                    </div>
                    {canEdit && (
                      <div className="flex shrink-0 gap-2">
                        <button type="button" className={BTN_CLASS} disabled={busy}
                          onClick={() => { setEditingId(row.staffing_config_id); setEditDraft(toDraft(row)) }}>
                          Edit
                        </button>
                        <button type="button" className={BTN_CLASS} disabled={busy}
                          onClick={() => run(() => api.deleteProjectStaffingConfig(project, row.staffing_config_id))}>
                          Remove
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>

          {canEdit && (
            <div className="space-y-2 border-t border-[var(--hb-border)] pt-3">
              <p className="text-sm font-medium">Add a staffing row</p>
              <DraftFields draft={addDraft} onChange={setAddDraft} />
              <div className="flex items-center gap-3">
                <button type="button" className={BTN_CLASS} disabled={busy}
                  onClick={() => run(async () => {
                    await api.createProjectStaffingConfig(project, { ...addDraft })
                    setAddDraft(EMPTY_DRAFT)
                  })}>
                  {busy ? 'Saving…' : 'Add row'}
                </button>
                {saveError && <span className="text-sm text-rose-300">{saveError}</span>}
              </div>
            </div>
          )}
        </div>
      )}
    </SectionCard>
  )
}
