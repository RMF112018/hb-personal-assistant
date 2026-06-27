import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { GitMerge, Scissors, UserCheck } from 'lucide-react'
import { useMemo, useState } from 'react'

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
import { EmptyState } from '../components/ui/EmptyState'
import * as api from '../lib/api'

function text(value: unknown, fallback = '—') {
  return value === null || value === undefined || value === '' ? fallback : String(value)
}

function shortKey(value: unknown) {
  const raw = text(value)
  return raw.length > 18 ? `${raw.slice(0, 9)}…${raw.slice(-6)}` : raw
}

export function ScheduleIdentityReviewPage() {
  const [projectKey, setProjectKey] = useScheduleProjectParam()
  const [targetByVersion, setTargetByVersion] = useState<Record<string, string>>({})
  const queryClient = useQueryClient()
  const enabled = Boolean(projectKey)
  const { data, isLoading, error } = useQuery({
    queryKey: ['schedules', 'identity-review', projectKey],
    queryFn: () => api.getScheduleIdentityReview(projectKey),
    enabled,
  })
  const payload = data && typeof data === 'object' ? (data as Record<string, unknown>) : {}
  const reviewItems = useMemo(
    () => (Array.isArray(payload.review_items) ? (payload.review_items as Record<string, unknown>[]) : []),
    [payload],
  )
  const identities = useMemo(
    () => (Array.isArray(payload.active_identities) ? (payload.active_identities as Record<string, unknown>[]) : []),
    [payload],
  )

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ['schedules', 'identity-review', projectKey] })
    queryClient.invalidateQueries({ queryKey: ['schedules', 'versions'] })
    queryClient.invalidateQueries({ queryKey: ['schedules', 'health-data'] })
  }

  const reassign = useMutation({
    mutationFn: ({ versionKey, targetIdentityKey }: { versionKey: string; targetIdentityKey: string }) =>
      api.reassignScheduleIdentity(projectKey, versionKey, targetIdentityKey, 'operator identity review'),
    onSuccess: invalidate,
  })
  const split = useMutation({
    mutationFn: (versionKey: string) =>
      api.splitScheduleIdentity(projectKey, versionKey, undefined, 'operator identity split'),
    onSuccess: invalidate,
  })
  const merge = useMutation({
    mutationFn: ({ sourceIdentityKey, targetIdentityKey }: { sourceIdentityKey: string; targetIdentityKey: string }) =>
      api.mergeScheduleIdentities(projectKey, sourceIdentityKey, targetIdentityKey, 'operator identity merge'),
    onSuccess: invalidate,
  })

  return (
    <ScheduleShell>
      <ScheduleBackLink />
      <ScheduleSubnav />
      <SchedulePageHeader
        title="Identity Review"
        subtitle="Resolve schedule versions that could not be safely attached to an existing schedule identity."
      />

      <div className="forecast-panel p-4 mb-4 max-w-3xl flex flex-wrap gap-3 items-end">
        <ScheduleProjectPicker value={projectKey} onChange={setProjectKey} className="min-w-[16rem]" />
      </div>

      {!projectKey ? <EmptyState title="Select a project" hint="Choose a project to review schedule identity matches." /> : null}
      {isLoading ? <p className="text-sm text-[var(--hb-muted)]">Loading identity review queue…</p> : null}
      {error ? <EmptyState title="Could not load identity review queue" /> : null}
      {projectKey && !isLoading && reviewItems.length === 0 ? (
        <EmptyState title="No identity review required" hint="All committed schedule versions are resolved for this project." />
      ) : null}

      {reviewItems.length > 0 ? (
        <ScheduleTable
          headers={
            <>
              <ScheduleTh>Version</ScheduleTh>
              <ScheduleTh>Evidence</ScheduleTh>
              <ScheduleTh>Status</ScheduleTh>
              <ScheduleTh>Assign / Merge</ScheduleTh>
              <ScheduleTh />
            </>
          }
        >
          {reviewItems.map((item) => {
            const versionKey = String(item.schedule_version_key)
            const currentIdentity = String(item.schedule_identity_key ?? '')
            const target = targetByVersion[versionKey] || ''
            const availableTargets = identities.filter((identity) => identity.schedule_identity_key !== currentIdentity)
            return (
              <tr key={versionKey}>
                <ScheduleTd>
                  <div className="font-mono text-xs">{shortKey(versionKey)}</div>
                  <div className="text-xs text-[var(--hb-muted)]">{text(item.source_filename_redacted ?? item.import_filename_redacted)}</div>
                </ScheduleTd>
                <ScheduleTd>
                  <div>{text(item.source_format)}</div>
                  <div className="text-xs text-[var(--hb-muted)]">
                    Activities {text(item.activity_count)} · Candidates {text(item.candidate_count)}
                  </div>
                </ScheduleTd>
                <ScheduleTd>
                  <div>{text(item.match_status)}</div>
                  <div className="text-xs text-[var(--hb-muted)]">{text(item.no_match_reason ?? item.match_rule)}</div>
                </ScheduleTd>
                <ScheduleTd>
                  <select
                    className="w-full rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] px-2 py-1.5 text-sm"
                    value={target}
                    onChange={(event) =>
                      setTargetByVersion((prev) => ({ ...prev, [versionKey]: event.target.value }))
                    }
                  >
                    <option value="">Select identity</option>
                    {availableTargets.map((identity) => (
                      <option
                        key={String(identity.schedule_identity_key)}
                        value={String(identity.schedule_identity_key)}
                      >
                        {text(identity.canonical_schedule_name ?? identity.latest_schedule_version_key ?? identity.schedule_identity_key)}
                      </option>
                    ))}
                  </select>
                </ScheduleTd>
                <ScheduleTd>
                  <div className="flex flex-wrap gap-2">
                    <ScheduleActionButton
                      variant="secondary"
                      disabled={!target || reassign.isPending}
                      onClick={() => reassign.mutate({ versionKey, targetIdentityKey: target })}
                    >
                      <UserCheck size={14} aria-hidden /> Assign
                    </ScheduleActionButton>
                    <ScheduleActionButton
                      variant="ghost"
                      disabled={split.isPending}
                      onClick={() => split.mutate(versionKey)}
                    >
                      <Scissors size={14} aria-hidden /> Split
                    </ScheduleActionButton>
                    <ScheduleActionButton
                      variant="ghost"
                      disabled={!target || merge.isPending}
                      onClick={() => merge.mutate({ sourceIdentityKey: currentIdentity, targetIdentityKey: target })}
                    >
                      <GitMerge size={14} aria-hidden /> Merge
                    </ScheduleActionButton>
                  </div>
                </ScheduleTd>
              </tr>
            )
          })}
        </ScheduleTable>
      ) : null}
    </ScheduleShell>
  )
}
