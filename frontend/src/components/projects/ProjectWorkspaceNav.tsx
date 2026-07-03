import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { ChevronDown } from 'lucide-react'

type ProjectWorkspaceNavProps = {
  projectKey: string
}

type ScheduleNavItem = {
  to: string
  label: string
}

export function ProjectWorkspaceNav({ projectKey }: ProjectWorkspaceNavProps) {
  const location = useLocation()
  const base = `/projects/${encodeURIComponent(projectKey)}`

  const flatItems = [
    { to: base, label: 'Overview' },
    { to: `${base}/forecasting`, label: 'Forecasting' },
    { to: `${base}/staffing`, label: 'Staffing' },
    { to: `${base}/exposures`, label: 'Exposures' },
  ]

  const scheduleBase = `${base}/schedule`
  const scheduleItems: ScheduleNavItem[] = [
    { to: scheduleBase, label: 'Schedule Overview' },
    { to: `${scheduleBase}/import`, label: 'Import Schedule' },
    { to: `${scheduleBase}/workbench`, label: 'Review Workbench' },
    { to: `${scheduleBase}/driver-detail`, label: 'Driver Detail' },
    { to: `${scheduleBase}/drivers`, label: 'Activity Drivers' },
  ]

  const isScheduleActive = location.pathname === scheduleBase || location.pathname.startsWith(`${scheduleBase}/`)

  // Dropdown state + a11y (modeled on the established ForecastMonthlyExportMenu pattern)
  const [scheduleOpen, setScheduleOpen] = useState(false)
  const scheduleContainerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!scheduleOpen) return
    const onPointerDown = (e: MouseEvent) => {
      if (scheduleContainerRef.current && !scheduleContainerRef.current.contains(e.target as Node)) {
        setScheduleOpen(false)
      }
    }
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setScheduleOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [scheduleOpen])

  // Close menu on route change (navigation occurred)
  useEffect(() => {
    setScheduleOpen(false)
  }, [location.pathname])

  const toggleSchedule = () => setScheduleOpen((v) => !v)

  return (
    <nav className="subnav" aria-label="Project workspace sections">
      {flatItems.map((item) => {
        const active = location.pathname === item.to
        return (
          <Link
            key={item.to}
            to={item.to}
            className={active ? 'active' : ''}
            aria-current={active ? 'page' : undefined}
          >
            {item.label}
          </Link>
        )
      })}

      {/* Schedule as grouped/dropdown nav (Phase 1 remediation) */}
      <div className="relative" ref={scheduleContainerRef}>
        <button
          type="button"
          className={`inline-flex items-center gap-1 rounded px-3 py-1 text-sm ${isScheduleActive ? 'active' : ''}`}
          aria-haspopup="menu"
          aria-expanded={scheduleOpen}
          aria-current={isScheduleActive ? 'page' : undefined}
          onClick={toggleSchedule}
        >
          Schedule
          <ChevronDown size={14} className={`transition-transform ${scheduleOpen ? 'rotate-180' : ''}`} aria-hidden />
        </button>

        {scheduleOpen && (
          <div
            role="menu"
            aria-label="Schedule"
            className="absolute left-0 z-50 mt-1 min-w-[14rem] rounded border border-[var(--hb-border)] bg-[var(--hb-bg)] py-1 shadow-md"
          >
            {scheduleItems.map((item) => {
              const itemActive = location.pathname === item.to || (item.to === scheduleBase && isScheduleActive)
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  role="menuitem"
                  className={`block px-3 py-1.5 text-sm hover:bg-black/10 ${itemActive ? 'font-medium text-[var(--hb-accent)]' : ''}`}
                  onClick={() => setScheduleOpen(false)}
                >
                  {item.label}
                </Link>
              )
            })}
          </div>
        )}
      </div>
    </nav>
  )
}
