import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AssistantPage } from './AssistantPage'

const recentChangesMock = vi.fn()
const staleCardsMock = vi.fn()
const sourcesMock = vi.fn()

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api')
  return {
    ...actual,
    api: {
      ...actual.api,
      getAssistantRecentChanges: (...args: unknown[]) => recentChangesMock(...args),
      getAssistantStaleCards: (...args: unknown[]) => staleCardsMock(...args),
      getAssistantSources: (...args: unknown[]) => sourcesMock(...args),
    },
  }
})

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter([{ path: '/assistant', element: <AssistantPage /> }], {
    initialEntries: ['/assistant'],
  })
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('AssistantPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    recentChangesMock.mockResolvedValue({
      changes: [
        {
          event_id: 'evt-1',
          source_id: 'src-1',
          rel_path: 'Mail/2026-07-01-note.eml',
          source_root_key: 'mail',
          event_type: 'new',
          status: 'processed',
          created_at: '2026-07-01T12:00:00Z',
        },
      ],
      count: 1,
      limit: 25,
      truncated: false,
    })
    staleCardsMock.mockResolvedValue({
      stale_cards: [{ source_id: 'src-2', note_rel_path: 'Projects/Tropical/Note.md' }],
      count: 1,
      limit: 25,
      truncated: false,
    })
    sourcesMock.mockResolvedValue({
      sources: [
        {
          result_type: 'source',
          source_id: 'src-3',
          path: 'Mail/procore-invoice.eml',
          project_key: 'tropical',
          score: 0.9,
          snippet: 'Invoice attached for review',
        },
      ],
      count: 1,
      limit: 25,
      truncated: false,
    })
  })

  it('renders recent changes and stale cards without searching', async () => {
    renderPage()
    expect(await screen.findByText('Mail/2026-07-01-note.eml')).toBeInTheDocument()
    expect(screen.getByText('Projects/Tropical/Note.md')).toBeInTheDocument()
    // Search query is disabled until the user types, so it must not fire on mount.
    expect(sourcesMock).not.toHaveBeenCalled()
  })

  it('runs a source search once the user types a query', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Mail/2026-07-01-note.eml')
    await user.type(screen.getByLabelText('Search sources'), 'invoice')
    expect(await screen.findByText('Mail/procore-invoice.eml')).toBeInTheDocument()
    expect(sourcesMock).toHaveBeenCalled()
  })
})
