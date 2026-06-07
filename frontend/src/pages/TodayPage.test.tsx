import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { TodayPage } from './TodayPage'

const useQueryMock = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: { queryKey: unknown[] }) => useQueryMock(options),
}))

function renderToday() {
  return render(
    <MemoryRouter>
      <TodayPage />
    </MemoryRouter>,
  )
}

function mockTodayQueries(overrides: {
  today?: Record<string, unknown>
  dailyBrief?: Record<string, unknown>
} = {}) {
  useQueryMock.mockImplementation(({ queryKey }: { queryKey: unknown[] }) => {
    const key = queryKey.join('/')
    if (key === 'today') {
      return {
        data: {
          metric_cards: [{ id: 'm1', label: 'Open priorities', value: 2 }],
          attention_items: [{ id: 'a1', title: 'Review submittal', when: 'Today', project: 'Tropical' }],
          freshness: { overall: 'fresh', minutes_ago_max: 12 },
          confidence_summary: { overall: 'source_backed' },
          project_count: 4,
          daily_brief: { status: 'brief_available' },
          ...overrides.today,
        },
        isLoading: false,
        error: null,
      }
    }
    if (key === 'today/daily-brief') {
      return {
        data: {
          status: 'brief_available',
          generated_at: 'Jun 7, 2026 at 8:00 AM',
          sections: { 'Executive Summary': 'Review priority items.' },
          ...overrides.dailyBrief,
        },
      }
    }
    if (key === 'today/meetings') return { data: { items: [{ subject: 'OAC meeting' }, { route: '/api/raw' }] } }
    if (key === 'today/action-items') return { data: { items: [{ title: 'Approve pay app' }] } }
    if (key === 'today/changes') return { data: { items: [{ description: 'New RFI response' }] } }
    if (key === 'today/portfolio-signals') return { data: { items: [{ project: 'Tropical', note: 'Budget review' }] } }
    return { data: null, isLoading: false, error: null }
  })
}

describe('TodayPage command center', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
  })

  it('renders dashboard sections in command-center order', () => {
    mockTodayQueries()
    renderToday()

    // 'Today' page label is visual text (non-heading) after PrimaryPageLayout standardization; card/section h3s remain headings.
    const headings = screen.getAllByRole('heading').map((heading) => heading.textContent)
    expect(headings).toEqual(expect.arrayContaining([
      'Priority Summary',
      'Daily Brief',
      'Meetings',
      'Action Items',
      'Recent Changes',
      'Correspondence',
      'Documents',
      'Cost / Change / Time',
    ]))
    expect(headings.indexOf('Priority Summary')).toBeLessThan(headings.indexOf('Daily Brief'))
    expect(headings.indexOf('Daily Brief')).toBeLessThan(headings.indexOf('Meetings'))
    expect(headings.indexOf('Meetings')).toBeLessThan(headings.indexOf('Action Items'))
    expect(headings.indexOf('Action Items')).toBeLessThan(headings.indexOf('Recent Changes'))
  })

  it('omits forbidden technical copy from normal Today UI', () => {
    mockTodayQueries()
    renderToday()

    const text = document.body.textContent || ''
    for (const forbidden of ['FastAPI', 'uvicorn', 'read model', 'source/sync/evidence', 'JSON.stringify', 'external Markdown', 'MCP']) {
      expect(text).not.toContain(forbidden)
    }
  })

  it('uses safe item fallback instead of raw JSON output', () => {
    mockTodayQueries()
    renderToday()

    expect(screen.getByText('Details unavailable')).toBeInTheDocument()
    expect(document.body.textContent).not.toContain('/api/raw')
  })

  it('points unavailable Daily Brief state to Settings', () => {
    mockTodayQueries({ dailyBrief: { content: undefined, sections: undefined, status: 'not_configured' } })
    renderToday()

    expect(screen.getByText('Brief not available yet.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open Settings' })).toHaveAttribute('href', '/settings')
  })

  it('renders safe error copy and Data Health action when Today cannot load', () => {
    useQueryMock.mockImplementation(({ queryKey }: { queryKey: unknown[] }) => {
      if (queryKey.join('/') === 'today') {
        return { data: null, isLoading: false, error: new Error('500 raw_backend_trace') }
      }
      return { data: null, isLoading: false, error: null }
    })

    renderToday()

    expect(screen.getByText('This section could not be loaded. Restart the local app and try again.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Check Data Health' })).toHaveAttribute('href', '/admin')
    expect(screen.getByText('500 raw_backend_trace')).not.toBeVisible()
  })
})
