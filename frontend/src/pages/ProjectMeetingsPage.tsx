/* eslint-disable @typescript-eslint/no-explicit-any */
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { FreshnessBadge, ConfidenceBadge } from '../components/ui/Badge'
import { ProjectSubNav } from '../components/projects/ProjectSubNav'
import { EmptyState } from '../components/ui/EmptyState'
import { api } from '../lib/api'

export function ProjectMeetingsPage() {
  const { projectKey = 'all' } = useParams()
  const key = projectKey || 'all'

  const { data: meetingsData, isLoading } = useQuery({
    queryKey: ['project', 'meetings', key],
    queryFn: () => api.getProjectMeetings(key),
  })

  if (isLoading) {
    return <div className="p-6 text-sm text-[var(--hb-muted)]">Loading meetings…</div>
  }

  const items = (meetingsData?.items || meetingsData || []) as any[]

  return (
    <div>
      <ProjectSubNav projectKey={key} />
      <div className="flex gap-2 mb-3">
        <FreshnessBadge status="fresh" />
        <ConfidenceBadge level="source_backed" />
      </div>
      <div className="card">
        <div className="section-title">Meetings Needing Prep / Recent</div>
        <p className="text-sm">Construction-native meeting list (prep status, attendees, linked items, Daily Brief context). No raw calendar payloads.</p>
        {items.length === 0 ? (
          <EmptyState title="No meeting data" hint="Calendar + Procore context will appear after sync." />
        ) : (
          <ul className="text-sm list-disc pl-4 mt-2 space-y-1">
            {items.slice(0, 8).map((m: any, i: number) => <li key={i}>{m.title || m.subject || JSON.stringify(m).slice(0, 100)}</li>)}
          </ul>
        )}
        <div className="text-xs mt-2 text-[var(--hb-muted)]">Uses calendar, Outlook, meeting action items, related files, related Procore context, and Daily Brief/meeting-prep context. Contextual under Projects (or All Projects). Not a top-level nav.</div>
      </div>
      <div className="mt-2 text-xs"><Link to="/my-items" className="underline">See My Items for personal meeting queue →</Link></div>
    </div>
  )
}
