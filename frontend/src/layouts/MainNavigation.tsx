import { Link } from 'react-router-dom'
import { PRIMARY_NAV, isActive } from '../navigation/navigationModel'
import { Calendar, FolderOpen, ListChecks } from 'lucide-react'

const iconFor = (label: string) => {
  if (label === 'Today') return <Calendar className="h-4 w-4" />
  if (label === 'Projects') return <FolderOpen className="h-4 w-4" />
  if (label === 'My Items') return <ListChecks className="h-4 w-4" />
  return null
}

export function MainNavigation({ currentPath }: { currentPath: string }) {
  return (
    <nav aria-label="Primary" className="space-y-1">
      {PRIMARY_NAV.map((item) => {
        const active = isActive(currentPath, item.route)
        return (
          <Link
            key={item.route}
            to={item.route}
            className={`nav-item ${active ? 'active' : ''}`}
            aria-current={active ? 'page' : undefined}
          >
            {iconFor(item.label)}
            <span>{item.label}</span>
          </Link>
        )
      })}
    </nav>
  )
}
