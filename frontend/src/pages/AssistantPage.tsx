/* Assistant — read-only second-brain browser (recent changes, stale cards, source search).
 * All data comes from the read-only GET /api/assistant/* surfaces. This page has no write actions:
 * no approve/reject/refresh/Qwen/graph controls — browsing only. */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import {
  ForecastHero,
  ForecastPanel,
  ForecastShell,
  ForecastTable,
  ForecastTd,
  ForecastTh,
} from '../components/forecast/ForecastPrimitives'
import { EmptyState } from '../components/ui/EmptyState'
import { api } from '../lib/api'

const INPUT = 'w-full rounded border border-[var(--hb-border)] bg-transparent px-2 py-1.5 text-sm'

export function AssistantPage() {
  const [q, setQ] = useState('')

  const {
    data: recentData,
    isLoading: recentLoading,
    error: recentError,
  } = useQuery({
    queryKey: ['assistant', 'recent-changes'],
    queryFn: () => api.getAssistantRecentChanges(25),
  })
  const changes = Array.isArray(recentData?.changes) ? recentData.changes : []

  const {
    data: staleData,
    isLoading: staleLoading,
    error: staleError,
  } = useQuery({
    queryKey: ['assistant', 'stale-cards'],
    queryFn: () => api.getAssistantStaleCards(25),
  })
  const staleCards = Array.isArray(staleData?.stale_cards) ? staleData.stale_cards : []

  const trimmedQ = q.trim()
  const {
    data: searchData,
    isLoading: searchLoading,
    error: searchError,
  } = useQuery({
    queryKey: ['assistant', 'sources', trimmedQ],
    queryFn: () => api.getAssistantSources(trimmedQ, { limit: 25 }),
    enabled: trimmedQ.length > 0,
  })
  const searchResults = Array.isArray(searchData?.sources) ? searchData.sources : []

  return (
    <ForecastShell>
      <ForecastHero
        eyebrow="Second brain"
        title="Assistant"
        subtitle="Read-only browser over sources, cards, and recent second-brain activity. Nothing here writes or mutates."
      />

      <ForecastPanel title="Search sources" description="Search indexed sources by keyword.">
        <label className="block text-sm mb-3 max-w-xl">
          <span className="text-[var(--hb-muted)]">Query</span>
          <input
            aria-label="Search sources"
            placeholder="Search sources…"
            className={`${INPUT} mt-1`}
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </label>

        {trimmedQ.length === 0 ? (
          <EmptyState title="Type to search" hint="Enter a keyword to search indexed sources." />
        ) : searchLoading ? (
          <p className="text-sm text-[var(--hb-muted)]">Searching…</p>
        ) : searchError ? (
          <EmptyState title="Could not search sources" />
        ) : searchResults.length === 0 ? (
          <EmptyState title="No matching sources" hint="Try a different keyword." />
        ) : (
          <ForecastTable
            headers={
              <>
                <ForecastTh>Path</ForecastTh>
                <ForecastTh>Project</ForecastTh>
                <ForecastTh>Type</ForecastTh>
                <ForecastTh>Score</ForecastTh>
                <ForecastTh>Snippet</ForecastTh>
              </>
            }
          >
            {searchResults.map((r, idx) => (
              <tr key={r.source_id || `${r.path}-${idx}`}>
                <ForecastTd>{r.path || '—'}</ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">{r.project_key || '—'}</ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">{r.result_type || '—'}</ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">{r.score ?? '—'}</ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">{r.snippet || '—'}</ForecastTd>
              </tr>
            ))}
          </ForecastTable>
        )}
      </ForecastPanel>

      <ForecastPanel title="Recent changes" description="Most recent second-brain source events.">
        {recentLoading ? (
          <p className="text-sm text-[var(--hb-muted)]">Loading recent changes…</p>
        ) : recentError ? (
          <EmptyState title="Could not load recent changes" />
        ) : changes.length === 0 ? (
          <EmptyState title="No recent changes" />
        ) : (
          <ForecastTable
            headers={
              <>
                <ForecastTh>Path</ForecastTh>
                <ForecastTh>Event</ForecastTh>
                <ForecastTh>Status</ForecastTh>
                <ForecastTh>Root</ForecastTh>
                <ForecastTh>Created</ForecastTh>
              </>
            }
          >
            {changes.map((c, idx) => (
              <tr key={c.event_id || `${c.source_id}-${idx}`}>
                <ForecastTd>{c.rel_path || '—'}</ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">{c.event_type || '—'}</ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">{c.status || '—'}</ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">{c.source_root_key || '—'}</ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">{c.created_at || '—'}</ForecastTd>
              </tr>
            ))}
          </ForecastTable>
        )}
      </ForecastPanel>

      <ForecastPanel title="Stale cards" description="Cards whose underlying source has changed since the card was written.">
        {staleLoading ? (
          <p className="text-sm text-[var(--hb-muted)]">Loading stale cards…</p>
        ) : staleError ? (
          <EmptyState title="Could not load stale cards" />
        ) : staleCards.length === 0 ? (
          <EmptyState title="No stale cards" hint="All cards are in sync with their sources." />
        ) : (
          <ForecastTable
            headers={
              <>
                <ForecastTh>Source</ForecastTh>
                <ForecastTh>Card path</ForecastTh>
              </>
            }
          >
            {staleCards.map((s, idx) => (
              <tr key={s.source_id || `${s.note_rel_path}-${idx}`}>
                <ForecastTd className="font-mono text-xs">{s.source_id || '—'}</ForecastTd>
                <ForecastTd>{s.note_rel_path || '—'}</ForecastTd>
              </tr>
            ))}
          </ForecastTable>
        )}
      </ForecastPanel>
    </ForecastShell>
  )
}
