import { Outlet, useLocation } from 'react-router-dom'
import { MainNavigation } from './MainNavigation'
import { PageHeader } from './PageHeader'
import { SidebarFooter } from '../components/layout/SidebarFooter'
import { useTheme } from '../app/providers'
import { Moon, Sun, Monitor, Menu } from 'lucide-react'
import { useState } from 'react'
import { HeaderNotificationsProvider, useHeaderNotifications } from './HeaderNotificationsContext'

export function AppShell({ children }: { children?: React.ReactNode }) {
  const { resolvedTheme, theme: prefTheme, toggle } = useTheme()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()

  // Simple construction-facing header title (advisory posture)
  const headerTitle = 'Personal Assistant'

  return (
    <div className="h-[100dvh] overflow-hidden flex bg-[var(--hb-bg)] text-[var(--hb-text)]">
      {/* Skip link for keyboard users (becomes visible on focus) */}
      <a
        href="#main"
        className="skip-link sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[100] focus:px-3 focus:py-1 focus:bg-[var(--hb-surface)] focus:border focus:border-[var(--hb-border)] focus:rounded focus:text-sm focus:outline-none"
      >
        Skip to main content
      </a>
      {/* Primary sidebar navigation (Today / Projects / My Items) — lightweight collapse for narrow widths */}
      <aside
        aria-label="Primary navigation"
        className={`fixed md:static inset-y-0 left-0 z-50 h-[100dvh] w-56 shrink-0 border-r border-[var(--hb-border)] p-3 flex flex-col min-h-0 overflow-hidden bg-[var(--hb-bg)] transform transition-transform duration-200 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}
      >
        <div className="px-2 py-3 text-xs tracking-[2px] text-[var(--hb-muted)] shrink-0">CONSTRUCTION INTELLIGENCE</div>
        <MainNavigation currentPath={location.pathname} />
        <SidebarFooter currentPath={location.pathname} />
      </aside>
      {/* Mobile sidebar overlay (click to close) */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/30 md:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Main content area */}
      <HeaderNotificationsProvider>
        <div className="flex-1 flex flex-col min-w-0 min-h-0 overflow-hidden">
          <header className="h-12 shrink-0 border-b border-[var(--hb-border)] px-4 flex items-center justify-between bg-[var(--hb-surface)]">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="md:hidden badge"
                aria-label="Toggle navigation"
                aria-expanded={sidebarOpen}
              >
                <Menu className="h-3.5 w-3.5" />
              </button>
              <div className="font-medium">{headerTitle}</div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={toggle}
                className="badge"
                title={`Theme: ${resolvedTheme} (click to cycle dark / light / system)`}
                aria-label="Toggle theme"
              >
                {resolvedTheme === 'dark' && <Moon className="h-3.5 w-3.5" />}
                {resolvedTheme === 'light' && <Sun className="h-3.5 w-3.5" />}
                {prefTheme === 'system' && <Monitor className="h-3.5 w-3.5" />}
                <span className="ml-1 capitalize">{resolvedTheme}</span>
              </button>
              <HeaderNotificationsSlot />
            </div>
          </header>

          <main id="main" className="flex-1 min-h-0 p-4 overflow-y-auto overflow-x-hidden">
            <PageHeader title={getPageTitle(location.pathname)} />
            {children ?? <Outlet />}
          </main>

          <footer className="shrink-0 text-[10px] px-4 py-2 border-t border-[var(--hb-border)] text-[var(--hb-muted)]">
            No determinations. All signals advisory. See Data Health for coverage and freshness.
          </footer>
        </div>
      </HeaderNotificationsProvider>
    </div>
  )
}

function getPageTitle(path: string): string {
  if (path.startsWith('/today')) return 'Today'
  if (path.startsWith('/projects/all/meetings') || path === '/projects/all/meetings') return 'All Projects • Meetings'
  if (path.startsWith('/projects/all/field-operations')) return 'All Projects • Field Operations'
  if (path.startsWith('/projects/all/cost-time')) return 'All Projects • Cost & Time'
  if (path.startsWith('/projects/all')) return 'All Projects'
  if (path.startsWith('/projects/')) return 'Project'
  if (path.startsWith('/projects')) return 'Projects'
  if (path.startsWith('/my-items')) return 'My Items'
  if (path.startsWith('/admin')) return 'Data Health'
  if (path.startsWith('/settings')) return 'Settings'
  if (path.startsWith('/get-started')) return 'Get Started'
  return 'Personal Assistant'
}

// Renders page-provided notifications/warnings (e.g. data quality chips) in the shell chrome header.
function HeaderNotificationsSlot() {
  const { notifications } = useHeaderNotifications()
  if (!notifications) return null
  return (
    <div className="flex items-center gap-1 text-xs" aria-label="Data quality notifications">
      {notifications}
    </div>
  )
}
