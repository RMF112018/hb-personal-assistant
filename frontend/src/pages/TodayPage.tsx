/* eslint-disable @typescript-eslint/no-explicit-any */
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { DashboardCard } from '../components/layout/DashboardCard'
import { DashboardGrid } from '../components/layout/DashboardGrid'
import { PrimaryPageLayout } from '../components/layout/PrimaryPageLayout'
import { SectionCard } from '../components/common/SectionCard'
import { ErrorState } from '../components/common/ErrorState'
import { MetricCard } from '../components/dashboard/MetricCard'
import { AttentionItemCard } from '../components/dashboard/AttentionItemCard'
import { StaleDataBanner } from '../components/ui/StaleDataBanner'
import { LoadingState } from '../components/common/LoadingState'
import { DailyBriefRenderer } from '../components/daily-brief/DailyBriefRenderer'
import { CheckDataHealthLink, SettingsLink } from '../components/today/TodayActions'
import { TodayList } from '../components/today/TodayList'
import { TodaySectionEmpty } from '../components/today/TodaySectionEmpty'
import { TodayStatusRow } from '../components/today/TodayStatusRow'
import { api } from '../lib/api'

// Today page (Prompt 09 / UI-09 + Prompt 17): primary landing with required sections (Important Today, What Changed, Today's Meetings, Action Items, Cost/Change/Time Signals, Documents & Correspondence Worth Reviewing, Daily Brief, compact Data Confidence context + header/day). 
// Daily Brief is external-MD only (present/polish; never generate/rewrite). All surfaces advisory. Cost/time language advisory only — not determinations.

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
    return <LoadingState label="Loading Today…" />
  }
  if (error) {
    return (
      <div className="space-y-3">
        <StaleDataBanner />
        <ErrorState
          error={error}
          userMessage="This section could not be loaded. Restart the local app and try again."
          actions={<CheckDataHealthLink />}
        />
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
    <PrimaryPageLayout
      actions={<CheckDataHealthLink />}
      status={<TodayStatusRow freshness={d.freshness} confidence={d.confidence_summary} projectCount={d.project_count} />}
    >
      <DashboardGrid columns="sections" gap="lg">
        <DashboardCard title="Priority Summary" span="full" tone={attention.length > 0 ? 'attention' : 'default'}>
          {metricCards.length === 0 && attention.length === 0 ? (
            <TodaySectionEmpty />
          ) : (
            <div className="space-y-3">
              <DashboardGrid columns="metrics">
                {metricCards.map((m: any, idx: number) => (
                  <MetricCard key={m.id || idx} label={m.label || m.name || 'Signal'} value={m.value ?? '—'} unit={m.unit} status={m.status} />
                ))}
              </DashboardGrid>
              <div className="grid gap-2">
                {attention.map((a: any, idx: number) => (
                  <AttentionItemCard key={a.id || idx} title={a.title || a.name || 'Needs attention'} when={a.when || a.age || 'Today'} project={a.project} />
                ))}
              </div>
            </div>
          )}
        </DashboardCard>

        <DashboardCard title="Daily Brief" span="wide">
          <DailyBriefRenderer
            content={fb.content || fb.markdown}
            status={fb.status || d.daily_brief?.status}
            generatedAt={fb.generated_at || fb.generatedAt}
            path={fb.path}
            warnings={fb.warnings}
            sections={fb.sections}
          />
        </DashboardCard>

        <DashboardCard title="Meetings">
          {meetingItems.length === 0 ? (
            <TodaySectionEmpty
              title="No meetings need attention right now."
              hint="Meeting prep and context will appear here when available."
              actions={<Link to="/projects" className="badge">Review Projects</Link>}
            />
          ) : (
            <TodayList items={meetingItems} limit={4} />
          )}
        </DashboardCard>

        <DashboardCard title="Action Items">
          {actionItemsList.length === 0 ? (
            <TodaySectionEmpty
              title="No items need attention right now."
              hint="Open and aging items for you will appear here."
              actions={<Link to="/my-dashboard" className="badge">Open My Dashboard</Link>}
            />
          ) : (
            <TodayList items={actionItemsList} />
          )}
        </DashboardCard>

        <SectionCard title="Recent Changes">
          {changeItems.length === 0 ? (
            <TodaySectionEmpty title="No recent changes need attention right now." />
          ) : (
            <TodayList items={changeItems} />
          )}
        </SectionCard>

        <SectionCard title="Correspondence">
          {portfolioItems.length === 0 ? (
            <TodaySectionEmpty
              title="No correspondence needs attention right now."
              hint="Project-matched messages worth review will appear here."
            />
          ) : (
            <TodayList items={portfolioItems} limit={4} />
          )}
        </SectionCard>

        <SectionCard title="Documents">
          {portfolioItems.length === 0 ? (
            <TodaySectionEmpty
              title="No document signals need attention right now."
              hint="Changed or review-worthy documents will appear here."
            />
          ) : (
            <TodayList items={portfolioItems} limit={4} />
          )}
        </SectionCard>

        <SectionCard title="Cost / Change / Time">
          {portfolioItems.length === 0 ? (
            <TodaySectionEmpty
              title="No cost, change, or time signals need attention right now."
              hint="Advisory budget, change, schedule, and procurement signals will appear here."
              actions={<CheckDataHealthLink />}
            />
          ) : (
            <TodayList items={portfolioItems} limit={4} />
          )}
        </SectionCard>
      </DashboardGrid>

      {(d.freshness?.overall === 'stale' || !today) && <StaleDataBanner />}
      <div className="mt-4 text-xs text-[var(--hb-muted)]">
        Need more detail? <Link to="/admin" className="underline">Check Data Health</Link> or <SettingsLink label="open Settings" />.
      </div>
    </PrimaryPageLayout>
  )
}
