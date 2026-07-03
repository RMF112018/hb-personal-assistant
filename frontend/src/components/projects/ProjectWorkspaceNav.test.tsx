import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { ProjectWorkspaceNav } from './ProjectWorkspaceNav'

vi.mock('../../lib/api', () => ({
  api: { getProjects: vi.fn() },
}))

function renderNav(initial = '/projects/tropical/schedule?as_of=2026-06-22&comparison_basis=prior_update') {
  const client = new QueryClient()
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initial]}>
        <Routes>
          <Route path="/projects/:projectKey/*" element={<ProjectWorkspaceNav projectKey="tropical" />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ProjectWorkspaceNav', () => {
  it('shows Manage Baselines in the schedule dropdown', async () => {
    const user = userEvent.setup()
    renderNav()
    await user.click(screen.getByRole('button', { name: /schedule/i }))
    expect(screen.getByRole('menuitem', { name: 'Manage Baselines' })).toBeInTheDocument()
  })

  it('preserves as_of on analytical schedule links', async () => {
    const user = userEvent.setup()
    renderNav()
    await user.click(screen.getByRole('button', { name: /schedule/i }))
    expect(screen.getByRole('menuitem', { name: 'Review Workbench' })).toHaveAttribute(
      'href',
      '/projects/tropical/schedule/workbench?as_of=2026-06-22&comparison_basis=prior_update',
    )
    expect(screen.getByRole('menuitem', { name: 'Manage Baselines' })).toHaveAttribute(
      'href',
      '/projects/tropical/schedule/baselines?as_of=2026-06-22&comparison_basis=prior_update',
    )
  })

  it('does not preserve as_of on import link', async () => {
    const user = userEvent.setup()
    renderNav()
    await user.click(screen.getByRole('button', { name: /schedule/i }))
    expect(screen.getByRole('menuitem', { name: 'Import Schedule' })).toHaveAttribute(
      'href',
      '/projects/tropical/schedule/import',
    )
  })
})
