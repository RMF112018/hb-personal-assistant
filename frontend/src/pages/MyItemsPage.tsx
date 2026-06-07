/* eslint-disable @typescript-eslint/no-explicit-any */
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { FreshnessBadge, ConfidenceBadge } from '../components/ui/Badge'
import { EmptyState } from '../components/ui/EmptyState'
import { MyActionItemCard } from '../components/my-items/MyActionItemCard'
import { api } from '../lib/api'

// My Items: user-specific filtered work queue (Prompt 09 / Prompt 19 polish).
// Not a replacement email client, calendar, or file browser.
// Prompt 16/19: aggregate /api/my-items only (backend implements no section subroutes).
// Explicit per-section arrays (my_action_items, my_meetings, ...) + attention_items with kinds
// are provided by the envelope for clean derivation without guessing.

interface MyAttentionItem {
  kind?: string
  title?: string
  subject?: string
  name?: string
  note?: string
  project?: string
  source?: string
  age?: string
  when?: string
  count?: number
}

interface MyItemsEnvelope {
  surface?: string
  metric_cards?: any[]
  attention_items?: MyAttentionItem[]
  my_action_items?: MyAttentionItem[]
  my_meetings?: MyAttentionItem[]
  my_correspondence?: MyAttentionItem[]
  my_files?: MyAttentionItem[]
  my_followed_projects?: MyAttentionItem[]
  sections?: string[]
  freshness?: { overall?: string; minutes_ago_max?: number }
  confidence_summary?: { overall?: string }
  project_keys?: string[]
  empty_stale_error?: string | null
}

export function MyItemsPage() {
  // Prompt 16/19: consume only the aggregate /api/my-items contract. The backend does not implement
  // the five section subroutes. Using the aggregate renders all five required sections with no 404s.
  const { data: my, isLoading } = useQuery({ queryKey: ['my-items'], queryFn: api.getMyItems })

  if (isLoading) {
    return <div className="p-6 text-sm text-[var(--hb-muted)]">Loading My Items…</div>
  }

  const myData: MyItemsEnvelope = (my as MyItemsEnvelope) || {}

  // Prefer explicit per-section arrays (Prompt 19 envelope); fall back to attention filter for compat.
  const actionsSrc: MyAttentionItem[] = (myData.my_action_items && myData.my_action_items.length > 0)
    ? myData.my_action_items
    : (myData.attention_items || []).filter((a) => (a.kind || '').includes('action') || (a.kind || '') === 'my_action')

  const attention: MyAttentionItem[] = Array.isArray(myData.attention_items) ? myData.attention_items : []

  // Direct lists for the other sections (explicit or empty)
  const meetingsSrc: MyAttentionItem[] = (myData.my_meetings && myData.my_meetings.length > 0)
    ? myData.my_meetings
    : (attention || []).filter((a) => (a.kind || '') === 'meeting')
  const correspondenceSrc: MyAttentionItem[] = (myData.my_correspondence && myData.my_correspondence.length > 0)
    ? myData.my_correspondence
    : (attention || []).filter((a) => (a.kind || '') === 'correspondence')
  const filesSrc: MyAttentionItem[] = (myData.my_files && myData.my_files.length > 0)
    ? myData.my_files
    : (attention || []).filter((a) => (a.kind || '') === 'file')
  const followedSrc: MyAttentionItem[] = (myData.my_followed_projects && myData.my_followed_projects.length > 0)
    ? myData.my_followed_projects
    : (attention || []).filter((a) => (a.kind || '') === 'followed_project')

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
          <EmptyState title="No action items" hint="Open/aging/review-required items assigned or relevant to you appear here after sources are connected and the first sync is approved (Admin)." />
        ) : (
          <div className="space-y-1">
            {actionsSrc.slice(0, 6).map((a: any, i: number) => (
              <MyActionItemCard
                key={i}
                title={a.title || a.description}
                source={a.source || a.project || '—'}
                age={a.age || a.when || ''}
                project={a.project}
                review={(a.kind || '') === 'review_required'}
              />
            ))}
          </div>
        )}
      </div>

      <div className="grid md:grid-cols-2 gap-3">
        <div className="card">
          <div className="section-title">My Meetings</div>
          {meetingsSrc.length === 0 ? (
            <EmptyState title="No meetings yet" hint="Today/upcoming meetings + prep status appear here once calendar + Procore sources are connected and the first sync is approved (Admin)." />
          ) : (
            <ul className="text-sm list-disc pl-4 space-y-1">
              {meetingsSrc.slice(0, 6).map((m: any, i: number) => <li key={i}>{m.title || m.note || m.kind}</li>)}
            </ul>
          )}
          <div className="text-xs mt-2 text-[var(--hb-muted)]">Prep context, related files, and Daily Brief references (when available). Contextual under My Items.</div>
        </div>
        <div className="card">
          <div className="section-title">My Correspondence</div>
          {correspondenceSrc.length === 0 ? (
            <EmptyState title="No correspondence to review" hint="Emails worth attention, stale threads, and waiting-on candidates (project-matched) surface here after Graph sources + first sync (Admin)." />
          ) : (
            <ul className="text-sm list-disc pl-4 space-y-1">
              {correspondenceSrc.slice(0, 6).map((c: any, i: number) => <li key={i}>{c.subject || c.title || c.note}</li>)}
            </ul>
          )}
          <div className="text-xs mt-2 text-[var(--hb-muted)]">Review-required signals only. No full mailbox. Drill to Admin for source details.</div>
        </div>
      </div>

      <div className="card">
        <div className="section-title">My Files</div>
        {filesSrc.length === 0 ? (
          <EmptyState title="No file signals" hint="OneDrive files recently changed or needing classification/review (tied to meetings/projects) appear here after connections and approved sync (Admin)." />
        ) : (
          <ul className="text-sm list-disc pl-4 space-y-1">
            {filesSrc.slice(0, 6).map((f: any, i: number) => <li key={i}>{f.name || f.path || f.note}</li>)}
          </ul>
        )}
        <div className="text-xs mt-2 text-[var(--hb-muted)]">Advisory only. No raw file contents or browser. Manage pins and coverage in Projects / Admin.</div>
      </div>

      <div className="card">
        <div className="section-title">My Followed Projects</div>
        {followedSrc.length === 0 && (myData.project_keys || []).length === 0 ? (
          <EmptyState title="No followed projects" hint="Pinned or followed project summaries and attention appear here. Manage pins in Projects; approve first sync (Admin) to populate signals." />
        ) : (
          <div className="text-sm">
            {(myData.project_keys || []).slice(0, 6).join(', ') || (followedSrc.length > 0 ? 'Followed projects have attention items.' : 'See Projects for pinned/followed.')}
            {' • '}<Link to="/projects" className="underline">Manage in Projects</Link>
          </div>
        )}
      </div>

      <div className="advisory">Hide full source evidence here; use Admin / Data Confidence for diagnostics, sync, and coverage.</div>
    </div>
  )
}
