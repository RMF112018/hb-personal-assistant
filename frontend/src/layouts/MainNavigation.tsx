import { Link } from 'react-router-dom'
import { PRIMARY_NAV, isActive } from '../navigation/navigationModel'
import { Calendar, FolderOpen, ListChecks, LayoutDashboard, TrendingUp } from 'lucide-react'

const iconFor = (label: string) => {
  if (label === 'My Dashboard') return <LayoutDashboard className="h-4 w-4" />
  if (label === 'Today') return <Calendar className="h-4 w-4" />
  if (label === 'Projects') return <FolderOpen className="h-4 w-4" />
  if (label === 'Forecasting') return <TrendingUp className="h-4 w-4" />
  if (label === 'My Items') return <ListChecks className="h-4 w-4" />
  return null
}

export function MainNavigation({ currentPath }: { currentPath: string }) {
  return (
    <nav aria-label="Primary" className="space-y-1">
      {PRIMARY_NAV.map((item) => {
        const active = isActive(currentPath, item.route)
        const hasChildren = !!item.children && item.children.length > 0
        if (hasChildren) {
          return (
            <div key={item.route}>
              <Link
                to={item.route}
                className={`nav-item ${active ? 'active' : ''}`}
                aria-current={active ? 'page' : undefined}
              >
                {iconFor(item.label)}
                <span>{item.label}</span>
              </Link>
              <ul className="ml-6 space-y-1 mt-1">
                {item.children!.map((child) => {
                  const childActive = isActive(currentPath, child.route)
                  return (
                    <li key={child.route}>
                      <Link
                        to={child.route}
                        className={`nav-item text-sm ${childActive ? 'active' : ''}`}
                        aria-current={childActive ? 'page' : undefined}
                      >
                        {iconFor(child.label)}
                        <span>{child.label}</span>
                      </Link>
                    </li>
                  )
                })}
              </ul>
            </div>
          )
        }
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
