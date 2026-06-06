/* eslint-disable @typescript-eslint/no-explicit-any */
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { FreshnessBadge, ConfidenceBadge } from '../components/ui/Badge'
import { ProjectSubNav } from '../components/projects/ProjectSubNav'
import { EmptyState } from '../components/ui/EmptyState'
import { api } from '../lib/api'

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
    return <div className="p-6 text-sm text-[var(--hb-muted)]">Loading {title}…</div>
  }

  const o = overview || {}
  const fb = o.freshness || {}
  const cb = o.confidence_summary || {}

  // 8 assistant-like overview sections (Prompt 09 + 11_)
  const sections = [
    { key: 'important_today', title: 'Important Today', hint: 'High-priority attention, aging decisions, exposure signals.' },
    { key: 'what_changed', title: 'What Changed', hint: 'Recent Procore, file, correspondence, and signal deltas.' },
    { key: 'action_items', title: 'Action Items', hint: 'Open, aging, review-required items for the project.' },
    { key: 'meetings_needing_prep', title: 'Meetings Needing Prep', hint: 'Upcoming meetings, prep status, linked context.' },
    { key: 'cost_time_signals', title: 'Cost & Time Signals', hint: 'Budget vs actual, change exposure, schedule variance.' },
    { key: 'field_operations_signals', title: 'Field Operations Signals', hint: 'Logs, observations, punch, inspections, quality/safety.' },
    { key: 'documents_correspondence', title: 'Documents / Correspondence Highlights', hint: 'Worth-review items, changes, decisions.' },
    { key: 'startup_closeout_billing', title: 'Startup / Closeout / Billing Attention', hint: 'Where applicable: readiness, blockers, attention.' },
  ]

  return (
    <div>
      <ProjectSubNav projectKey={key} />
      <div className="flex items-center gap-2 mb-3">
        <FreshnessBadge status={fb.overall || 'unknown'} minutesAgo={fb.minutes_ago_max} />
        <ConfidenceBadge level={cb.overall || 'not_available'} />
        <span className="text-xs text-[var(--hb-muted)] ml-2">advisory • contextual tabs only</span>
        <Link to="/admin" className="text-xs underline ml-auto">Detailed source/sync/evidence → Admin / Data Confidence</Link>
      </div>

      <div className="card mb-3">
        <div className="section-title">{title} • Overview</div>
        <p className="text-sm">{o.summary || 'Important items, recent changes, attention, and key metrics composed from read models.'}</p>
        <div className="text-xs mt-2">Meetings, Field Operations, and Cost &amp; Time are available as contextual sections (see tabs above). Documents, correspondence, vendors, billing, schedule, procurement, RFIs, submittals, and design decisions appear inside these or Admin as needed. No top-level domain navs.</div>
      </div>

      <div className="grid md:grid-cols-2 gap-3">
        {sections.map((s) => {
          const items = (o[s.key] || o[s.key.replace(/_/g, '')] || []) as any[]
          return (
            <div key={s.key} className="card">
              <div className="section-title">{s.title}</div>
              {items && items.length > 0 ? (
                <ul className="text-sm list-disc pl-4 space-y-1">
                  {items.slice(0, 5).map((it: any, i: number) => <li key={i}>{it.title || it.description || JSON.stringify(it).slice(0, 90)}</li>)}
                </ul>
              ) : (
                <div className="text-sm text-[var(--hb-muted)]">{s.hint}</div>
              )}
            </div>
          )
        })}
      </div>

      {!overview && <EmptyState title="No overview data" hint="Approve sync (Admin) or refresh sources for this project." />}
    </div>
  )
}
