/* eslint-disable @typescript-eslint/no-explicit-any */
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { EmptyState } from '../components/common/EmptyState'
import { LoadingState } from '../components/common/LoadingState'
import { DashboardGrid } from '../components/layout/DashboardGrid'
import { PrimaryPageLayout } from '../components/layout/PrimaryPageLayout'
import { ProjectConnectionsLink } from '../components/projects/ProjectActions'
import { ProjectStatusRow } from '../components/projects/ProjectStatusRow'
import { ProjectSubNav } from '../components/projects/ProjectSubNav'
import { SectionCard } from '../components/common/SectionCard'
import { api } from '../lib/api'
import { safeDisplayText } from '../lib/errorCopy'

export function ProjectDashboardPage() {
  const { projectKey = 'all' } = useParams()
  const isAll = projectKey === 'all'
  const key = projectKey || 'all'
  const title = isAll ? 'All Projects' : `Project ${projectKey}`

  const { data: overview, isLoading } = useQuery({
    queryKey: ['project', 'overview', key],
    queryFn: () => api.getProjectOverview(key),
  })

  if (isLoading) {
    return <LoadingState label={`Loading ${title}`} />
  }

  const o = overview || {}

  const sections = [
    { key: 'important_today', title: 'Needs attention', hint: 'No items need attention right now.' },
    { key: 'what_changed', title: 'Recently updated', hint: 'No recent updates are available yet.' },
    { key: 'action_items', title: 'Action Items', hint: 'No open action items are visible yet.' },
    { key: 'meetings_needing_prep', title: 'Meetings', hint: 'No meetings need preparation right now.' },
    { key: 'cost_time_signals', title: 'Cost & Time', hint: 'Cost and schedule signals will appear after connected data is approved.' },
    { key: 'field_operations_signals', title: 'Field Operations', hint: 'Field activity will appear after connected data is approved.' },
    { key: 'documents_correspondence', title: 'Documents and Correspondence', hint: 'Documents and correspondence highlights will appear here.' },
    { key: 'startup_closeout_billing', title: 'Startup, Closeout, and Billing', hint: 'No startup, closeout, or billing items need attention right now.' },
  ]

  return (
    <PrimaryPageLayout
      status={
        <ProjectStatusRow
          freshness={o.freshness}
          confidence={o.confidence_summary}
          projectCount={isAll ? o.project_count : 1}
        />
      }
      actions={<ProjectConnectionsLink />}
    >
      <ProjectSubNav projectKey={key} />

      <SectionCard title="Project overview" description="Current project signals in one place.">
        <p className="text-sm">
          {typeof o.summary === 'string' && o.summary.trim().length > 0
            ? o.summary
            : 'Project overview will appear after project data is connected and approved.'}
        </p>
      </SectionCard>

      <DashboardGrid columns="sections">
        {sections.map((section) => {
          const items = getSectionItems(o, section.key)
          return (
            <SectionCard key={section.key} title={section.title}>
              {items.length > 0 ? (
                <ul className="list-disc space-y-1 pl-4 text-sm">
                  {items.slice(0, 5).map((item: any, index: number) => (
                    <li key={index}>{safeDisplayText(item)}</li>
                  ))}
                </ul>
              ) : (
                <div className="text-sm text-[var(--hb-muted)]">{section.hint}</div>
              )}
            </SectionCard>
          )
        })}
      </DashboardGrid>

      {!overview && (
        <EmptyState
          title="No project overview yet."
          hint="Review project connections in Settings."
          actions={<ProjectConnectionsLink />}
        />
      )}
    </PrimaryPageLayout>
  )
}

function getSectionItems(overview: any, key: string) {
  const compactKey = key.replace(/_/g, '')
  const items = overview?.[key] || overview?.[compactKey] || []
  return Array.isArray(items) ? items : []
}
