import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { MyItemsPage } from './MyItemsPage'

const useQueryMock = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: { queryKey: unknown[] }) => useQueryMock(options),
}))

function renderMyItems() {
  return render(
    <MemoryRouter>
      <MyItemsPage />
    </MemoryRouter>,
  )
}

function mockMyItems(data: Record<string, unknown> = {}) {
  useQueryMock.mockReturnValue({
    data: {
      my_action_items: [{ title: 'Review pay application', project: 'Tropical', age: 'Today' }],
      my_meetings: [{ subject: 'OAC meeting', when: 'Tomorrow' }],
      my_correspondence: [{ subject: 'Submittal response' }],
      my_files: [{ name: 'Updated drawing set' }],
      my_followed_projects: [{ title: 'Tropical priority review', project: 'Tropical' }],
      project_keys: ['tropical'],
      freshness: { overall: 'fresh', minutes_ago_max: 5 },
      confidence_summary: { overall: 'source_backed' },
      ...data,
    },
    isLoading: false,
    error: null,
  })
}

describe('MyItemsPage work queue', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
  })

  it('renders work-queue sections in priority order', () => {
    mockMyItems()
    renderMyItems()

    // Chrome header owns the page title. Primary body label removed; the queue cards/sections provide the h3 headings.
    const headings = screen.getAllByRole('heading').map((heading) => heading.textContent)
    expect(headings).toEqual(expect.arrayContaining([
      'My Action Items',
      'My Meetings',
      'My Correspondence',
      'My Files',
      'My Followed Projects',
    ]))
    expect(headings.indexOf('My Action Items')).toBeLessThan(headings.indexOf('My Meetings'))
    expect(headings.indexOf('My Meetings')).toBeLessThan(headings.indexOf('My Correspondence'))
    expect(headings.indexOf('My Correspondence')).toBeLessThan(headings.indexOf('My Files'))
    expect(headings.indexOf('My Files')).toBeLessThan(headings.indexOf('My Followed Projects'))
  })

  it('renders empty action guidance with Settings action', () => {
    mockMyItems({
      my_action_items: [],
      my_meetings: [],
      my_correspondence: [],
      my_files: [],
      my_followed_projects: [],
      project_keys: [],
    })
    renderMyItems()

    expect(screen.getByText('No action items need your attention.')).toBeInTheDocument()
    expect(screen.getByText('Connect Microsoft 365 and Procore in Settings to populate this list.')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Open Settings' })[0]).toHaveAttribute('href', '/settings')
  })

  it('renders sample data and keeps Projects reachable', () => {
    mockMyItems()
    renderMyItems()

    expect(screen.getByText('Review pay application')).toBeInTheDocument()
    expect(screen.getByText('OAC meeting')).toBeInTheDocument()
    expect(screen.getByText('Submittal response')).toBeInTheDocument()
    expect(screen.getByText('Updated drawing set')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Open Projects' })[0]).toHaveAttribute('href', '/projects')
  })

  it('uses safe fallback text for object-like items', () => {
    mockMyItems({ my_action_items: [{ route: '/api/raw-object' }] })
    renderMyItems()

    expect(screen.getByText('Details unavailable')).toBeInTheDocument()
    expect(document.body.textContent).not.toContain('/api/raw-object')
  })

  it('renders source-agnostic loading and error states', () => {
    useQueryMock.mockReturnValue({ data: null, isLoading: true, error: null })
    const { unmount } = renderMyItems()
    expect(screen.getByText('Loading My Items')).toBeInTheDocument()
    unmount()

    useQueryMock.mockReturnValue({ data: null, isLoading: false, error: new Error('Graph diagnostics failed') })
    renderMyItems()
    expect(screen.getByText('We could not load your work queue.')).toBeInTheDocument()
    expect(screen.getByText('Graph diagnostics failed')).not.toBeVisible()
  })

  it('omits forbidden implementation copy from normal My Items UI', () => {
    mockMyItems()
    renderMyItems()

    const text = document.body.textContent || ''
    for (const forbidden of [
      'Graph',
      'diagnostics',
      'Admin',
      'source evidence',
      'source details',
      'first sync',
      'Outlook + Procore + local review state',
      'JSON.stringify',
    ]) {
      expect(text).not.toContain(forbidden)
    }
  })
})
