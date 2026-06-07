import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ProjectsPage } from './ProjectsPage'

const useQueryMock = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: { queryKey: unknown[] }) => useQueryMock(options),
}))

function renderProjects() {
  return render(
    <MemoryRouter>
      <ProjectsPage />
    </MemoryRouter>,
  )
}

function mockPortfolio(data: Record<string, unknown> = {}) {
  useQueryMock.mockReturnValue({
    data: {
      projects: [
        { key: 'tropical', name: 'Tropical', status: 'active', freshness_status: 'fresh' },
        { key: 'setup-project', name: 'Setup Project', status: 'needs_setup', freshness_status: 'unknown' },
      ],
      freshness: { overall: 'fresh', minutes_ago_max: 10 },
      confidence_summary: { overall: 'source_backed' },
      ...data,
    },
    isLoading: false,
    error: null,
  })
}

describe('ProjectsPage command center', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
  })

  it('renders command-center sections in target order', () => {
    mockPortfolio()
    renderProjects()

    // Chrome header owns the page title. Primary body label removed; card/section titles are the h3 headings.
    const headings = screen.getAllByRole('heading').map((heading) => heading.textContent)
    expect(headings).toEqual(expect.arrayContaining([
      'Active Projects',
      'Projects that need setup',
      'Recently updated projects',
      'Project Connections',
      'All Projects',
    ]))
    expect(headings.indexOf('Active Projects')).toBeLessThan(headings.indexOf('Projects that need setup'))
    expect(headings.indexOf('Projects that need setup')).toBeLessThan(headings.indexOf('Recently updated projects'))
    expect(headings.indexOf('Recently updated projects')).toBeLessThan(headings.indexOf('Project Connections'))
    expect(headings.indexOf('Project Connections')).toBeLessThan(headings.indexOf('All Projects'))
  })

  it('renders empty setup guidance with Settings action', () => {
    mockPortfolio({ projects: [], project_keys: [] })
    renderProjects()

    expect(screen.getByText('No active projects are connected yet.')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Review project connections in Settings' })[0]).toHaveAttribute('href', '/settings')
    expect(screen.getAllByText('Project data will appear after sources are connected and approved.').length).toBeGreaterThan(0)
  })

  it('keeps project cards and All Projects routes reachable', () => {
    mockPortfolio()
    renderProjects()

    expect(screen.getAllByRole('link', { name: /Tropical/ })[0]).toHaveAttribute('href', '/projects/tropical')
    expect(screen.getAllByRole('link', { name: 'Open All Projects' })[0]).toHaveAttribute('href', '/projects/all')
  })

  it('omits forbidden implementation copy from normal Projects UI', () => {
    mockPortfolio()
    renderProjects()

    const text = document.body.textContent || ''
    for (const forbidden of ['contextual tabs', 'read model', 'source/sync/evidence', 'JSON.stringify', 'Admin / Data Confidence']) {
      expect(text).not.toContain(forbidden)
    }
  })
})
