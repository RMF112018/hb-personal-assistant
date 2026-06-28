import { Link, useLocation } from 'react-router-dom'

type ProjectWorkspaceNavProps = {
  projectKey: string
}

export function ProjectWorkspaceNav({ projectKey }: ProjectWorkspaceNavProps) {
  const location = useLocation()
  const base = `/projects/${encodeURIComponent(projectKey)}`
  const items = [
    { to: base, label: 'Overview' },
    { to: `${base}/forecasting`, label: 'Forecasting' },
    { to: `${base}/schedule`, label: 'Schedule' },
    { to: `${base}/staffing`, label: 'Staffing' },
    { to: `${base}/exposures`, label: 'Exposures' },
  ]

  return (
    <nav className="subnav" aria-label="Project workspace sections">
      {items.map((item) => {
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
    </nav>
  )
}
