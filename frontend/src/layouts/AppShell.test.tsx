import { render, screen, within, cleanup } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { describe, expect, test, beforeEach, vi } from 'vitest'

import { ThemeProvider } from '../app/providers'
import { AppShell } from './AppShell'

vi.mock('../components/layout/DataQualityIndicator', () => ({
  DataQualityIndicator: () => <div>Data Quality</div>,
}))

function renderShell(path = '/today') {
  const router = createMemoryRouter(
    [
      {
        path: '*',
        element: (
          <AppShell>
            <div>Page content</div>
          </AppShell>
        ),
      },
    ],
    { initialEntries: [path] }
  )
  return render(
    <ThemeProvider>
      <RouterProvider router={router} />
    </ThemeProvider>,
  )
}

describe('AppShell production chrome', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  test('renders Schedules in primary navigation', () => {
    renderShell('/schedules/imports')
    expect(screen.getByRole('link', { name: /Schedules/i })).toBeInTheDocument()
  })

  test('does not render development role chrome or disabled chat navigation', () => {
    renderShell()

    expect(screen.queryByText(/Local dev role/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/not production auth/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Chat/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/\(disabled\)/i)).not.toBeInTheDocument()
  })

  test('renders the sidebar data quality status area for non-admin and hides for admin', () => {
    // Non-admin (default operator): Data Quality indicator visible in footer.
    renderShell()
    expect(screen.getByText('Data Quality')).toBeInTheDocument()

    // Cleanup previous render tree before role change + admin render (prevents DOM accumulation across renders in single test).
    cleanup()

    // Admin role: indicator gated out (SidebarFooter); Data Health nav item present instead.
    window.localStorage.setItem('hb-ui-role', 'admin')
    const adminRouter = createMemoryRouter(
      [
        {
          path: '*',
          element: (
            <AppShell>
              <div>Page content</div>
            </AppShell>
          ),
        },
      ],
      { initialEntries: ['/today'] }
    )
    const { unmount } = render(
      <ThemeProvider>
        <RouterProvider router={adminRouter} />
      </ThemeProvider>,
    )
    expect(screen.queryByText('Data Quality')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Data Health/i })).toBeInTheDocument()
    unmount()
  })

  test('hides Admin support navigation for viewer and operator roles', () => {
    window.localStorage.setItem('hb-ui-role', 'viewer')
    renderShell('/settings')

    expect(screen.queryByRole('link', { name: /Data Health/i })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Settings/i })).toBeInTheDocument()
  })

  test('shows active Admin support navigation for admin role', () => {
    window.localStorage.setItem('hb-ui-role', 'admin')
    renderShell('/admin')

    const adminLink = screen.getByRole('link', { name: /Data Health/i })
    expect(adminLink).toHaveAttribute('aria-current', 'page')
  })

  test('preserves active Settings support navigation', () => {
    renderShell('/settings')

    const supportNav = screen.getByRole('navigation', { name: /Support/i })
    const settingsLink = within(supportNav).getByRole('link', { name: /Settings/i })
    expect(settingsLink).toHaveAttribute('aria-current', 'page')
  })

  test('renders dynamic page title from route in chrome header (replacing static brand)', () => {
    renderShell('/today')
    // The chrome header (top bar) now owns the active title; sr-only h1 in main for a11y.
    // Scope to the header to avoid matching the nav child label "Today" or the sr-only h1.
    const header = document.querySelector('header') as HTMLElement
    expect(within(header).getByText('Today')).toBeInTheDocument()

    // Verify a different route resolves a different title in chrome
    // (re-render with new path via new shell instance to keep test isolated)
    const projectsRouter = createMemoryRouter(
      [
        {
          path: '*',
          element: (
            <AppShell>
              <div>Page content</div>
            </AppShell>
          ),
        },
      ],
      { initialEntries: ['/projects'] }
    )
    const { unmount, container: projectsContainer } = render(
      <ThemeProvider>
        <RouterProvider router={projectsRouter} />
      </ThemeProvider>,
    )
    const projectsHeader = projectsContainer.querySelector('header') as HTMLElement
    expect(within(projectsHeader).getByText('Projects')).toBeInTheDocument()
    unmount()
  })
})
