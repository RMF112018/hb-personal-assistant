import { Outlet, useLocation } from 'react-router-dom'
import { MainNavigation } from './MainNavigation'
import { SupportNavigation } from './SupportNavigation'
import { PageHeader } from './PageHeader'
import { useTheme } from '../app/providers'
import { Moon, Sun, Monitor } from 'lucide-react'

export function AppShell({ children }: { children?: React.ReactNode }) {
  const { resolvedTheme, theme: prefTheme, toggle } = useTheme()
  const location = useLocation()

  // Simple construction-facing header title (advisory posture)
  const headerTitle = 'HB Analytics'

  return (
    <div className="min-h-screen flex bg-[var(--hb-bg)] text-[var(--hb-text)]">
      {/* Primary sidebar navigation (Today / Projects / My Items) */}
      <aside className="w-56 border-r border-[var(--hb-border)] p-3 flex flex-col">
        <div className="px-2 py-3 text-xs tracking-[2px] text-[var(--hb-muted)]">CONSTRUCTION INTELLIGENCE</div>
        <MainNavigation currentPath={location.pathname} />
        <div className="mt-auto pt-4">
          <SupportNavigation currentPath={location.pathname} />
        </div>
      </aside>

      {/* Main content area */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-12 border-b border-[var(--hb-border)] px-4 flex items-center justify-between bg-[var(--hb-surface)]">
          <div className="font-medium">{headerTitle}</div>
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
            <div className="text-[10px] text-[var(--hb-muted)]">Advisory only • Local-first</div>
          </div>
        </header>

        <main className="flex-1 p-4 overflow-auto">
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
