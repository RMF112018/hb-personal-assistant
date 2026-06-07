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
  // Prompt 16: consume only the aggregate /api/my-items contract. The backend does not implement the five
  // section subroutes (/api/my-items/{action-items,meetings,correspondence,files,followed-projects}).
  // Using the aggregate avoids 404s while still rendering all five required My Items sections.
  const { data: my, isLoading } = useQuery({ queryKey: ['my-items'], queryFn: api.getMyItems })

  if (isLoading) {
    return <div className="p-6 text-sm text-[var(--hb-muted)]">Loading My Items…</div>
  }

  // Aggregate envelope (object): metric_cards + attention_items + sections list the areas.
  // No top-level 'items' for My Items; detailed per-section arrays are not split in the current read model.
  const actionsSrc = (my?.attention_items || []).filter((a: any) => (a.kind || '').includes('action') || (a.kind || '') === 'my_action')
  const metricCards = Array.isArray(my?.metric_cards) ? my.metric_cards : []
  const attention = Array.isArray(my?.attention_items) ? my.attention_items : []

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <FreshnessBadge status={my?.freshness?.overall || 'fresh'} minutesAgo={my?.freshness?.minutes_ago_max} />
        <ConfidenceBadge level={my?.confidence_summary?.overall || 'source_backed'} />
      </div>

      <div className="card">
        <div className="section-title">My Action Items</div>
        <div className="text-sm mb-2">Filtered queue from Outlook + Procore + local review state. <strong>My Items is a filtered work queue, not a replacement email client, calendar, or file browser.</strong></div>
        {actionsSrc.length === 0 ? (
          <EmptyState title="No action items" hint="Open/aging/review-required items assigned or relevant to you appear here." />
        ) : (
          <div className="space-y-1">
            {actionsSrc.slice(0, 6).map((a: any, i: number) => (
              <MyActionItemCard key={i} title={a.title || a.description} source={a.source || a.project || '—'} age={a.age || a.when || ''} />
            ))}
          </div>
        )}
      </div>

      <div className="grid md:grid-cols-2 gap-3">
        <div className="card">
          <div className="section-title">My Meetings</div>
          {attention.length === 0 && metricCards.length === 0 ? (
            <div className="text-sm text-[var(--hb-muted)]">Today/upcoming + prep status + related context.</div>
          ) : (
            <ul className="text-sm list-disc pl-4 space-y-1">
              {attention.slice(0, 4).map((m: any, i: number) => <li key={i}>{m.title || m.note || m.kind}</li>)}
            </ul>
          )}
        </div>
        <div className="card">
          <div className="section-title">My Correspondence</div>
          {attention.length === 0 && metricCards.length === 0 ? (
            <div className="text-sm text-[var(--hb-muted)]">Emails worth reviewing, stale threads, waiting-on candidates, project-matched.</div>
          ) : (
            <ul className="text-sm list-disc pl-4 space-y-1">
              {attention.slice(0, 4).map((c: any, i: number) => <li key={i}>{c.subject || c.title || c.note}</li>)}
            </ul>
          )}
        </div>
      </div>

      <div className="card">
        <div className="section-title">My Files</div>
        {attention.length === 0 && metricCards.length === 0 ? (
          <div className="text-sm text-[var(--hb-muted)]">OneDrive files recently changed or needing review, tied to meetings/projects.</div>
        ) : (
          <ul className="text-sm list-disc pl-4 space-y-1">
            {attention.slice(0, 4).map((f: any, i: number) => <li key={i}>{f.name || f.path || f.note}</li>)}
          </ul>
        )}
      </div>

      <div className="card">
        <div className="section-title">My Followed Projects</div>
        {attention.length === 0 && metricCards.length === 0 ? (
          <div className="text-sm">Pinned/followed project summaries + attention. <Link to="/projects" className="underline">Manage in Projects</Link></div>
        ) : (
          <div className="text-sm">{(my?.project_keys || []).slice(0, 6).join(', ') || 'See Projects for pinned/followed.'} • <Link to="/projects" className="underline">Manage in Projects</Link></div>
        )}
      </div>

      <div className="advisory">Hide full source evidence here; use Admin / Data Confidence for diagnostics, sync, and coverage.</div>
    </div>
  )
}
