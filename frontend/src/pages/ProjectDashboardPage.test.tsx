import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ProjectDashboardPage } from './ProjectDashboardPage'

const useQueryMock = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: { queryKey: unknown[] }) => useQueryMock(options),
}))

function renderProjectDashboard(path = '/projects/tropical') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/projects/:projectKey" element={<ProjectDashboardPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

function mockOverview(data: Record<string, unknown> = {}) {
  useQueryMock.mockReturnValue({
    data: {
      summary: 'Project overview for current work.',
      freshness: { overall: 'fresh', minutes_ago_max: 8 },
      confidence_summary: { overall: 'source_backed' },
      important_today: [{ route: '/api/raw-object' }],
      what_changed: [{ title: 'New RFI response' }],
      ...data,
    },
    isLoading: false,
  })
}

describe('ProjectDashboardPage', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
  })

  it('preserves project detail navigation links', () => {
    mockOverview()
    renderProjectDashboard()

    expect(screen.getByRole('link', { name: 'Overview' })).toHaveAttribute('href', '/projects/tropical')
    expect(screen.getByRole('link', { name: 'Meetings' })).toHaveAttribute('href', '/projects/tropical/meetings')
    expect(screen.getByRole('link', { name: 'Field Operations' })).toHaveAttribute('href', '/projects/tropical/field-operations')
    expect(screen.getByRole('link', { name: 'Cost & Time' })).toHaveAttribute('href', '/projects/tropical/cost-time')
  })

  it('uses safe fallback copy for object-like list items', () => {
    mockOverview()
    renderProjectDashboard()

    expect(screen.getByText('Details unavailable')).toBeInTheDocument()
    expect(document.body.textContent).not.toContain('/api/raw-object')
  })

  it('omits forbidden implementation copy from normal Project Dashboard UI', () => {
    mockOverview()
    renderProjectDashboard()

    const text = document.body.textContent || ''
    for (const forbidden of ['contextual tabs', 'read model', 'source/sync/evidence', 'JSON.stringify', 'Admin / Data Confidence']) {
      expect(text).not.toContain(forbidden)
    }
  })

  it('renders setup guidance when overview data is absent', () => {
    useQueryMock.mockReturnValue({ data: null, isLoading: false })
    renderProjectDashboard()

    expect(screen.getByText('No project overview yet.')).toBeInTheDocument()
    expect(screen.getByText('Review project connections in Settings.')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Review project connections in Settings' })[0]).toHaveAttribute('href', '/settings')
  })
})
