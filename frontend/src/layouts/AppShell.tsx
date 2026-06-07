import { Outlet, useLocation } from 'react-router-dom'
import { MainNavigation } from './MainNavigation'
import { SupportNavigation } from './SupportNavigation'
import { PageHeader } from './PageHeader'
import { useTheme } from '../app/providers'
import { Moon, Sun, Monitor, Menu } from 'lucide-react'
import { useState } from 'react'
import { getLocalUiRole, setLocalUiRole, type LocalUiRole } from '../lib/api'

export function AppShell({ children }: { children?: React.ReactNode }) {
  const { resolvedTheme, theme: prefTheme, toggle } = useTheme()
  const [localRole, setLocalRole] = useState<LocalUiRole>(() => getLocalUiRole())
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()

  // Simple construction-facing header title (advisory posture)
  const headerTitle = 'HB Analytics'

  return (
    <div className="min-h-screen flex bg-[var(--hb-bg)] text-[var(--hb-text)]">
      {/* Skip link for keyboard users (becomes visible on focus) */}
      <a
        href="#main"
        className="skip-link sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[100] focus:px-3 focus:py-1 focus:bg-[var(--hb-surface)] focus:border focus:border-[var(--hb-border)] focus:rounded focus:text-sm focus:outline-none"
      >
        Skip to main content
      </a>
      {/* Primary sidebar navigation (Today / Projects / My Items) — lightweight collapse for narrow widths */}
      <aside
        className={`fixed md:static inset-y-0 left-0 z-50 w-56 border-r border-[var(--hb-border)] p-3 flex flex-col bg-[var(--hb-bg)] transform transition-transform duration-200 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}
      >
        <div className="px-2 py-3 text-xs tracking-[2px] text-[var(--hb-muted)]">CONSTRUCTION INTELLIGENCE</div>
        <MainNavigation currentPath={location.pathname} />
        <div className="mt-auto pt-4">
          <SupportNavigation currentPath={location.pathname} />
        </div>
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
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-12 border-b border-[var(--hb-border)] px-4 flex items-center justify-between bg-[var(--hb-surface)]">
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
            <label className="flex items-center gap-1 text-[10px] text-[var(--hb-muted)]">
              Local dev role — not production auth
              <select
                className="badge bg-[var(--hb-surface)]"
                value={localRole}
                onChange={(event) => {
                  const next = event.target.value as LocalUiRole
                  setLocalUiRole(next)
                  setLocalRole(next)
                }}
                aria-label="Local dev role"
              >
                <option value="viewer">Viewer</option>
                <option value="operator">Operator</option>
                <option value="admin">Admin</option>
              </select>
            </label>
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
            <div className="text-[10px] text-[var(--hb-muted)]">Advisory only • Local-first</div>
          </div>
        </header>

        <main id="main" className="flex-1 p-4 overflow-auto">
          <PageHeader title={getPageTitle(location.pathname)} />
          {children ?? <Outlet />}
        </main>

        <footer className="text-[10px] px-4 py-2 border-t border-[var(--hb-border)] text-[var(--hb-muted)]">
          No determinations. All signals advisory. See Admin / Data Confidence for source, sync, evidence, and retrieval details.
        </footer>
      </div>
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
  if (path.startsWith('/admin')) return 'Admin / Data Confidence'
  if (path.startsWith('/settings')) return 'Settings'
  return 'HB Analytics'
}
