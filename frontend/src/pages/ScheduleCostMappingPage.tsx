import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import {
  ScheduleActionButton,
  ScheduleBackLink,
  SchedulePageHeader,
  ScheduleShell,
  ScheduleSubnav,
  ScheduleTable,
  ScheduleTd,
  ScheduleTh,
} from '../components/schedule/SchedulePageChrome'
import {
  ScheduleProjectPicker,
  useScheduleProjectParam,
} from '../components/schedule/ScheduleProjectPicker'
import { ScheduleVersionPicker } from '../components/schedule/ScheduleVersionPicker'
import { api } from '../lib/api'

const OBJECTIVES = [
  { id: 'association_only', label: 'Associate activities to cost codes only' },
  { id: 'simplified_duration_distribution', label: 'Simplified duration-based distribution (analytical)' },
  { id: 'true_cost_loading', label: 'True cost loading from financial records' },
  { id: 'existing_cost_loaded_review', label: 'Review existing cost-loaded schedule' },
]

export function ScheduleCostMappingPage() {
  const [projectKey, setProjectKey] = useScheduleProjectParam()
  const queryClient = useQueryClient()
  const [objective, setObjective] = useState('association_only')
  const [versionKey, setVersionKey] = useState('')
  const [run, setRun] = useState<Record<string, unknown> | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const mappingRunId = run?.mapping_run_id ? String(run.mapping_run_id) : ''

  const { data: weightingBefore } = useQuery({
    queryKey: ['schedules', 'weighting', projectKey],
    queryFn: () => api.getScheduleCostWeighting(projectKey),
  })

  const { data: candidatesData, refetch: refetchCandidates } = useQuery({
    queryKey: ['schedules', 'candidates', mappingRunId],
    queryFn: () => api.getScheduleCostMappingCandidates(mappingRunId),
    enabled: Boolean(mappingRunId),
  })

  const candidates = Array.isArray((candidatesData as { candidates?: unknown[] })?.candidates)
    ? (candidatesData as { candidates: Record<string, unknown>[] }).candidates
    : []

  const weightCountBefore = Array.isArray(
    (weightingBefore as { weighting_results?: unknown[] })?.weighting_results,
  )
    ? (weightingBefore as { weighting_results: unknown[] }).weighting_results.length
    : 0

  async function startRun() {
    if (!versionKey) return
    setBusy(true)
    setMessage(null)
    try {
      const resp = await api.createScheduleCostMappingRun(projectKey, versionKey, objective)
      setRun(resp as Record<string, unknown>)
    } finally {
      setBusy(false)
    }
  }

  async function reviewCandidate(candidateId: number, status: string) {
    setBusy(true)
    try {
      await api.reviewScheduleCostMappingCandidate(candidateId, { operator_status: status })
      await refetchCandidates()
    } finally {
      setBusy(false)
    }
  }

  async function approveRun() {
    if (!mappingRunId) return
    setBusy(true)
    setMessage(null)
    try {
      const resp = await api.approveScheduleCostMappingRun(mappingRunId)
      setRun((prev) => ({ ...(prev || {}), ...(resp as Record<string, unknown>) }))
      await queryClient.invalidateQueries({ queryKey: ['schedules', 'weighting', projectKey] })
      const weightAfter = await api.getScheduleCostWeighting(projectKey)
      const count = Array.isArray((weightAfter as { weighting_results?: unknown[] })?.weighting_results)
        ? (weightAfter as { weighting_results: unknown[] }).weighting_results.length
        : 0
      setMessage(`Run approved. Weighting entries: ${count} (was ${weightCountBefore} before approval).`)
    } catch {
      setMessage('Approval failed. Ensure at least one candidate is approved when required.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <ScheduleShell>
      <ScheduleBackLink />
      <ScheduleSubnav />
      <SchedulePageHeader
        title="Cost mapping"
        subtitle="Choose your mapping objective and approve candidates before any schedule-to-cost association becomes active."
      />

      <div className="forecast-panel p-4 space-y-4 text-sm">
        <ScheduleProjectPicker value={projectKey} onChange={setProjectKey} className="max-w-md" />
        <ScheduleVersionPicker projectKey={projectKey} value={versionKey} onChange={setVersionKey} />

        <p className="font-medium">What are you trying to accomplish with this schedule mapping?</p>
        <div className="space-y-2">
          {OBJECTIVES.map((o) => (
            <label key={o.id} className="flex items-start gap-2">
              <input
                type="radio"
                name="objective"
                value={o.id}
                checked={objective === o.id}
                onChange={() => setObjective(o.id)}
              />
              <span>{o.label}</span>
            </label>
          ))}
        </div>
        <ScheduleActionButton onClick={() => void startRun()} disabled={busy || !versionKey}>
          Start mapping run
        </ScheduleActionButton>

        {run ? (
          <p>
            Mapping run <code>{mappingRunId}</code> — status {String(run.mapping_status)}
            {run.distribution_label ? ` · ${String(run.distribution_label)}` : ''}
          </p>
        ) : null}

        {candidates.length > 0 ? (
          <>
            <ScheduleTable
              headers={
                <>
                  <ScheduleTh>Activity</ScheduleTh>
                  <ScheduleTh>Cost code</ScheduleTh>
                  <ScheduleTh>Status</ScheduleTh>
                  <ScheduleTh />
                </>
              }
            >
              {candidates.map((c) => (
                <tr key={String(c.id)}>
                  <ScheduleTd>{String(c.activity_id)}</ScheduleTd>
                  <ScheduleTd>{String(c.candidate_cost_code ?? '')}</ScheduleTd>
                  <ScheduleTd>{String(c.operator_status ?? 'pending')}</ScheduleTd>
                  <ScheduleTd>
                    <div className="flex gap-1">
                      <button
                        type="button"
                        className="forecast-btn-ghost text-xs"
                        disabled={busy}
                        onClick={() => void reviewCandidate(Number(c.id), 'approved')}
                      >
                        Approve
                      </button>
                      <button
                        type="button"
                        className="forecast-btn-ghost text-xs"
                        disabled={busy}
                        onClick={() => void reviewCandidate(Number(c.id), 'rejected')}
                      >
                        Reject
                      </button>
                    </div>
                  </ScheduleTd>
                </tr>
              ))}
            </ScheduleTable>
            <ScheduleActionButton onClick={() => void approveRun()} disabled={busy || !mappingRunId}>
              Approve mapping run
            </ScheduleActionButton>
          </>
        ) : null}

        {message ? <p className="text-[var(--hb-muted)]">{message}</p> : null}
        <p className="text-[var(--hb-muted)]">
          Current approved weighting entries: {weightCountBefore}
        </p>
      </div>
    </ScheduleShell>
  )
}