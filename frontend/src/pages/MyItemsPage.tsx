/* eslint-disable @typescript-eslint/no-explicit-any */
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { FreshnessBadge, ConfidenceBadge } from '../components/ui/Badge'
import { EmptyState } from '../components/ui/EmptyState'
import { MyActionItemCard } from '../components/my-items/MyActionItemCard'
import { api } from '../lib/api'

// My Items: user-specific filtered work queue (Prompt 09).
// Not a replacement email client, calendar, or file browser.

export function MyItemsPage() {
  const { data: my, isLoading } = useQuery({ queryKey: ['my-items'], queryFn: api.getMyItems })
  const { data: myActions } = useQuery({ queryKey: ['my-items', 'action-items'], queryFn: api.getMyItemsActionItems })
  const { data: myMeetings } = useQuery({ queryKey: ['my-items', 'meetings'], queryFn: api.getMyItemsMeetings })
  const { data: myCorr } = useQuery({ queryKey: ['my-items', 'correspondence'], queryFn: api.getMyItemsCorrespondence })
  const { data: myFiles } = useQuery({ queryKey: ['my-items', 'files'], queryFn: api.getMyItemsFiles })
  const { data: myFollowed } = useQuery({ queryKey: ['my-items', 'followed-projects'], queryFn: api.getMyItemsFollowedProjects })

  if (isLoading) {
    return <div className="p-6 text-sm text-[var(--hb-muted)]">Loading My Items…</div>
  }

  const actions = (myActions?.items || myActions || []) as any[]
  const meetings = (myMeetings?.items || myMeetings || []) as any[]
  const corr = (myCorr?.items || myCorr || []) as any[]
  const files = (myFiles?.items || myFiles || []) as any[]
  const followed = (myFollowed?.items || myFollowed || []) as any[]

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <FreshnessBadge status={my?.freshness?.overall || 'fresh'} minutesAgo={my?.freshness?.minutes_ago_max} />
        <ConfidenceBadge level={my?.confidence_summary?.overall || 'source_backed'} />
      </div>

      <div className="card">
        <div className="section-title">My Action Items</div>
        <div className="text-sm mb-2">Filtered queue from Outlook + Procore + local review state. <strong>My Items is a filtered work queue, not a replacement email client, calendar, or file browser.</strong></div>
        {actions.length === 0 ? (
          <EmptyState title="No action items" hint="Open/aging/review-required items assigned or relevant to you appear here." />
        ) : (
          <div className="space-y-1">
            {actions.slice(0, 6).map((a: any, i: number) => (
              <MyActionItemCard key={i} title={a.title || a.description} source={a.source || a.project || '—'} age={a.age || a.when || ''} />
            ))}
          </div>
        )}
      </div>

      <div className="grid md:grid-cols-2 gap-3">
        <div className="card">
          <div className="section-title">My Meetings</div>
          {meetings.length === 0 ? <div className="text-sm text-[var(--hb-muted)]">Today/upcoming + prep status + related context.</div> : (
            <ul className="text-sm list-disc pl-4 space-y-1">{meetings.slice(0, 4).map((m: any, i: number) => <li key={i}>{m.title || m.subject}</li>)}</ul>
          )}
        </div>
        <div className="card">
          <div className="section-title">My Correspondence</div>
          {corr.length === 0 ? <div className="text-sm text-[var(--hb-muted)]">Emails worth reviewing, stale threads, waiting-on candidates, project-matched.</div> : (
            <ul className="text-sm list-disc pl-4 space-y-1">{corr.slice(0, 4).map((c: any, i: number) => <li key={i}>{c.subject || c.title}</li>)}</ul>
          )}
        </div>
      </div>

      <div className="card">
        <div className="section-title">My Files</div>
        {files.length === 0 ? <div className="text-sm text-[var(--hb-muted)]">OneDrive files recently changed or needing review, tied to meetings/projects.</div> : (
          <ul className="text-sm list-disc pl-4 space-y-1">{files.slice(0, 4).map((f: any, i: number) => <li key={i}>{f.name || f.path}</li>)}</ul>
        )}
      </div>

      <div className="card">
        <div className="section-title">My Followed Projects</div>
        {followed.length === 0 ? (
          <div className="text-sm">Pinned/followed project summaries + attention. <Link to="/projects" className="underline">Manage in Projects</Link></div>
        ) : (
          <div className="text-sm">{followed.map((p: any) => p.name || p.key).join(', ')} • <Link to="/projects" className="underline">Manage in Projects</Link></div>
        )}
      </div>

      <div className="advisory">Hide full source evidence here; use Admin / Data Confidence for diagnostics, sync, and coverage.</div>
    </div>
  )
}
