/* eslint-disable @typescript-eslint/no-explicit-any */
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { FreshnessBadge, ConfidenceBadge } from '../components/ui/Badge'
import { MetricCard } from '../components/dashboard/MetricCard'
import { AttentionItemCard } from '../components/dashboard/AttentionItemCard'
import { EmptyState } from '../components/ui/EmptyState'
import { StaleDataBanner } from '../components/ui/StaleDataBanner'
import { DailyBriefRenderer } from '../components/daily-brief/DailyBriefRenderer'
import { api } from '../lib/api'

// Today page (Prompt 09 / UI-09): primary landing with 6 sections driven from Prompt 07 read models.
// Daily Brief is external-MD only (present/polish; never generate/rewrite). All surfaces advisory.

export function TodayPage() {
  const { data: today, isLoading, error } = useQuery({
    queryKey: ['today'],
    queryFn: api.getToday,
  })

  const { data: dailyBrief } = useQuery({
    queryKey: ['today', 'daily-brief'],
    queryFn: api.getTodayDailyBrief,
  })

  // Optional granular fetches for the other sections (today family)
  const { data: changes } = useQuery({ queryKey: ['today', 'changes'], queryFn: api.getTodayChanges })
  const { data: meetings } = useQuery({ queryKey: ['today', 'meetings'], queryFn: api.getTodayMeetings })
  const { data: actionItems } = useQuery({ queryKey: ['today', 'action-items'], queryFn: api.getTodayActionItems })
  const { data: portfolioSignals } = useQuery({ queryKey: ['today', 'portfolio-signals'], queryFn: api.getTodayPortfolioSignals })

  if (isLoading) {
    return <div className="p-6 text-sm text-[var(--hb-muted)]">Loading Today…</div>
  }
  if (error) {
    return (
      <div className="space-y-3">
        <StaleDataBanner />
        <EmptyState title="Unable to load Today" hint="Start the FastAPI analytics shell (pip install -e '.[analytics-ui]'; uvicorn ...) or check connection. All data advisory." />
        <div className="text-xs"><Link to="/admin" className="underline">Open Admin / Data Confidence →</Link></div>
      </div>
    )
  }

  const d = today || {}
  const fb = dailyBrief || {}

  const metricCards = Array.isArray(d.metric_cards) ? d.metric_cards : []
  const attention = Array.isArray(d.attention_items) ? d.attention_items : []

  // Safe extraction for the other sections (shape depends on exact envelope; render what we can)
  const changeItems = Array.isArray(changes?.items) ? changes.items.slice(0, 6) : (changes ? [changes] : [])
  const meetingItems = Array.isArray(meetings?.items) ? meetings.items.slice(0, 4) : (meetings ? [meetings] : [])
  const actionItemsList = Array.isArray(actionItems?.items) ? actionItems.items.slice(0, 6) : (actionItems ? [actionItems] : [])
  const portfolioItems = Array.isArray(portfolioSignals?.items) ? portfolioSignals.items.slice(0, 4) : (portfolioSignals ? [portfolioSignals] : [])

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <FreshnessBadge status={d.freshness?.overall || 'unknown'} minutesAgo={d.freshness?.minutes_ago_max} />
        <ConfidenceBadge level={d.confidence_summary?.overall || 'not_available'} />
        <span className="text-xs text-[var(--hb-muted)]">{d.project_count ?? '—'} projects • advisory</span>
        <Link to="/admin" className="text-xs underline ml-auto">View source &amp; sync details →</Link>
      </div>

      {/* Important Today */}
      <section>
        <div className="section-title">Important Today</div>
        {metricCards.length === 0 && attention.length === 0 ? (
          <EmptyState title="No signals" hint="Data will appear after sources sync. See Admin for freshness." />
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
              {metricCards.map((m: any, idx: number) => (
                <MetricCard key={m.id || idx} label={m.label || m.name} value={m.value} unit={m.unit} status={m.status} />
              ))}
            </div>
            <div className="mt-3 grid gap-2">
              {attention.map((a: any, idx: number) => (
                <AttentionItemCard key={a.id || idx} title={a.title} when={a.when || a.age} project={a.project} />
              ))}
            </div>
          </>
        )}
      </section>

      {/* Daily Brief — external Markdown only (present/polish contract, Prompt 10) */}
      <section>
        <div className="section-title">Daily Brief</div>
        <DailyBriefRenderer
          content={fb.content || fb.markdown}
          status={fb.status || d.daily_brief?.status}
          generatedAt={fb.generated_at || fb.generatedAt}
          path={fb.path}
          warnings={fb.warnings}
          sections={fb.sections}
        />
        <div className="advisory mt-2">
          Source: externally generated Markdown file. The app presents/polishes only and does not generate or materially rewrite content.
          States: Not configured • External AI setup required • Configured (waiting) • Brief available • Brief stale • Brief generation failed • Markdown parse warning.
          <span className="ml-2"><a className="underline" href="#/settings">Configure folder / platform in Settings →</a></span>
        </div>
        {fb.path && (
          <div className="text-[10px] text-[var(--hb-muted)] mt-1">File: {fb.path} {fb.generated_at ? `• ${fb.generated_at}` : ''}</div>
        )}
      </section>

      {/* Today's Meetings */}
      <section>
        <div className="section-title">Today's Meetings</div>
        {meetingItems.length === 0 ? (
          <div className="card text-sm">No meetings data in current window. Prep readiness and context appear here after sync. <Link to="/projects" className="underline">Review in Projects →</Link></div>
        ) : (
          <div className="grid gap-2">
            {meetingItems.map((m: any, idx: number) => (
              <div key={idx} className="card text-sm">{m.title || m.subject || JSON.stringify(m).slice(0, 120)}</div>
            ))}
          </div>
        )}
        <div className="text-xs mt-1"><Link to="/my-items" className="underline">See My Items for personal meeting queue →</Link></div>
      </section>

      {/* What Changed + Action Items + Portfolio Signals (driven from today family where available) */}
      <section className="grid md:grid-cols-3 gap-3">
        <div className="card">
          <div className="section-title">What Changed</div>
          {changeItems.length === 0 ? (
            <div className="text-sm text-[var(--hb-muted)]">Recent Procore, file, correspondence, and signal deltas will appear here.</div>
          ) : (
            <ul className="text-sm list-disc pl-4 space-y-1">
              {changeItems.map((c: any, idx: number) => <li key={idx}>{c.title || c.description || JSON.stringify(c).slice(0, 80)}</li>)}
            </ul>
          )}
        </div>
        <div className="card">
          <div className="section-title">Action Items</div>
          {actionItemsList.length === 0 ? (
            <div className="text-sm">Open and aging items for the current user. <Link to="/my-items" className="underline">Open My Items →</Link></div>
          ) : (
            <ul className="text-sm list-disc pl-4 space-y-1">
              {actionItemsList.map((a: any, idx: number) => <li key={idx}>{a.title || a.description || JSON.stringify(a).slice(0, 80)}</li>)}
            </ul>
          )}
        </div>
        <div className="card">
          <div className="section-title">Portfolio Signals</div>
          {portfolioItems.length === 0 ? (
            <div className="text-sm">Projects needing attention, cost exposure, schedule/procurement, closeout/billing signals. See Admin for full diagnostics.</div>
          ) : (
            <ul className="text-sm list-disc pl-4 space-y-1">
              {portfolioItems.map((p: any, idx: number) => <li key={idx}>{p.title || p.project || JSON.stringify(p).slice(0, 80)}</li>)}
            </ul>
          )}
        </div>
      </section>

      {(d.freshness?.overall === 'stale' || !today) && <StaleDataBanner />}
      <div className="text-[10px] text-[var(--hb-muted)]">Data from composed read models (Prompt 07). Hide detailed source/sync/evidence here; link to Admin / Data Confidence.</div>
    </div>
  )
}
