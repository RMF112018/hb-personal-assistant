import { Link, useLocation } from 'react-router-dom'

export function ProjectSubNav({ projectKey }: { projectKey: string }) {
  const loc = useLocation()
  const base = projectKey === 'all' ? '/projects/all' : `/projects/${projectKey}`
  const items = [
    { to: base, label: 'Overview' },
    { to: `${base}/meetings`, label: 'Meetings' },
    { to: `${base}/field-operations`, label: 'Field Operations' },
    { to: `${base}/cost-time`, label: 'Cost & Time' },
  ]
  return (
    <nav className="subnav" aria-label="Project sections">
      {items.map((it) => {
        const active = loc.pathname === it.to || (it.to === base && loc.pathname === base)
        return (
          <Link key={it.to} to={it.to} className={active ? 'active' : ''}>
            {it.label}
          </Link>
        )
      })}
    </nav>
  )
}
