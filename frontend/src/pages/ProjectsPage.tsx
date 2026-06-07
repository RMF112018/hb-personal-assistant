/* eslint-disable @typescript-eslint/no-explicit-any */
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { FreshnessBadge, ConfidenceBadge } from '../components/ui/Badge'
import { EmptyState } from '../components/ui/EmptyState'
import { api } from '../lib/api'

// /projects = Portfolio dashboard + project selector (All Projects special entry + individuals).
// Support backend project_keys list or legacy projects/items array.
// No top-level domain navs; contextual tabs only inside project or All views.

export function ProjectsPage() {
  const { data: portfolio, isLoading } = useQuery({
    queryKey: ['projects', 'portfolio'],
    queryFn: api.getProjectsPortfolio,
  })

  if (isLoading) {
    return <div className="p-6 text-sm text-[var(--hb-muted)]">Loading Portfolio…</div>
  }

  // Support backend project_keys list or legacy projects/items array.
  // If project_keys present and no legacy array content, map keys to minimal cards.
  let individuals: any[] = []
  const raw = portfolio?.projects || portfolio?.items || portfolio
  if (Array.isArray(raw) && raw.length > 0) {
    individuals = raw
  } else if (portfolio?.project_keys && Array.isArray(portfolio.project_keys)) {
    individuals = portfolio.project_keys.map((k: string) => ({ key: k, name: k, status: 'active' }))
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2 items-center">
        <FreshnessBadge status={portfolio?.freshness?.overall || 'unknown'} minutesAgo={portfolio?.freshness?.minutes_ago_max} />
        <ConfidenceBadge level={portfolio?.confidence_summary?.overall || 'not_available'} />
        <Link to="/projects/all" className="ml-auto underline text-sm">View All Projects aggregated →</Link>
      </div>

      {/* Project selector: All Projects (aggregated) + individual active/followed projects */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {/* All Projects special entry */}
        <Link to="/projects/all" className="card hover:border-[var(--hb-accent)] block">
          <div className="font-medium">All Projects</div>
          <div className="text-xs text-[var(--hb-muted)] mt-1">Aggregated overview across active projects • Meetings • Field Operations • Cost &amp; Time (contextual tabs)</div>
          <div className="text-[10px] mt-2 text-[var(--hb-muted)]">Click for portfolio-wide signals, attention, and drilldowns.</div>
        </Link>

        {individuals.length === 0 ? (
          <EmptyState title="No projects" hint="Connect sources and approve first sync (Admin). Individual projects appear here with freshness." />
        ) : (
          individuals.map((p: any, idx: number) => {
            const key = p.key || p.project_key || p.id || `p-${idx}`
            const name = p.name || p.display_name || key
            const status = p.status || p.health || 'active'
            const fr = p.freshness || p.freshness_status || portfolio?.freshness?.overall || 'unknown'
            return (
              <Link key={key} to={`/projects/${encodeURIComponent(key)}`} className="card hover:border-[var(--hb-accent)] block">
                <div className="font-medium">{name}</div>
                <div className="text-xs text-[var(--hb-muted)] flex items-center gap-2 mt-1">
                  <span className="badge">{status}</span>
                  <FreshnessBadge status={fr} compact />
                </div>
                <div className="text-[10px] mt-2 text-[var(--hb-muted)]">Overview • Meetings • Field Ops • Cost &amp; Time (contextual tabs only)</div>
              </Link>
            )
          })
        )}
      </div>

      <div className="text-xs">Portfolio view. Meetings, Cost, Field Operations, Documents, Correspondence, Vendors, Billing, Closeout etc. are inside individual project or All Projects surfaces (via tabs). No top-level nav for them.</div>
    </div>
  )
}
