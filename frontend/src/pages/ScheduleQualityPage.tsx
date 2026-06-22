import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'

import {
  ScheduleBackLink,
  SchedulePageHeader,
  ScheduleShell,
  ScheduleSubnav,
  ScheduleTable,
  ScheduleTd,
  ScheduleTh,
} from '../components/schedule/SchedulePageChrome'
import {
  DEFAULT_SCHEDULE_PROJECT,
  ScheduleVersionPicker,
} from '../components/schedule/ScheduleVersionPicker'
import { EmptyState } from '../components/ui/EmptyState'
import { api } from '../lib/api'

export function ScheduleQualityPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [versionKey, setVersionKey] = useState(searchParams.get('version') || '')

  useEffect(() => {
    setVersionKey(searchParams.get('version') || '')
  }, [searchParams])

  const { data, isLoading, error } = useQuery({
    queryKey: ['schedules', 'quality', versionKey],
    queryFn: () => api.getScheduleQuality(versionKey),
    enabled: Boolean(versionKey),
  })

  const findings = Array.isArray((data as { findings?: unknown[] })?.findings)
    ? (data as { findings: Record<string, unknown>[] }).findings
    : []

  function onVersionChange(next: string) {
    setVersionKey(next)
    if (next) setSearchParams({ version: next })
    else setSearchParams({})
  }

  return (
    <ScheduleShell>
      <ScheduleBackLink />
      <ScheduleSubnav />
      <SchedulePageHeader
        title="Schedule quality"
        subtitle="Quality findings from committed schedule imports."
      />

      <div className="forecast-panel p-4 mb-3 max-w-xl">
        <ScheduleVersionPicker
          projectKey={DEFAULT_SCHEDULE_PROJECT}
          value={versionKey}
          onChange={onVersionChange}
        />
      </div>

      {!versionKey ? (
        <EmptyState title="Select a schedule version" hint="Choose a version to review quality findings." />
      ) : null}
      {isLoading ? <p className="text-sm text-[var(--hb-muted)]">Loading findings…</p> : null}
      {error ? <EmptyState title="Could not load quality findings" /> : null}
      {versionKey && !isLoading && findings.length === 0 ? (
        <EmptyState title="No quality findings" hint="This version passed quality checks." />
      ) : null}

      {findings.length > 0 ? (
        <ScheduleTable
          headers={
            <>
              <ScheduleTh>Severity</ScheduleTh>
              <ScheduleTh>Code</ScheduleTh>
              <ScheduleTh>Message</ScheduleTh>
              <ScheduleTh>Activity</ScheduleTh>
            </>
          }
        >
          {findings.map((f, i) => (
            <tr key={i}>
              <ScheduleTd>{String(f.severity ?? '')}</ScheduleTd>
              <ScheduleTd>{String(f.finding_code ?? f.code ?? '')}</ScheduleTd>
              <ScheduleTd>{String(f.message ?? '')}</ScheduleTd>
              <ScheduleTd>{String(f.activity_id ?? '—')}</ScheduleTd>
            </tr>
          ))}
        </ScheduleTable>
      ) : null}
    </ScheduleShell>
  )
}