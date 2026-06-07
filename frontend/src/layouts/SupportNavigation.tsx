import { Link } from 'react-router-dom'
import { SUPPORT_NAV, isActive } from '../navigation/navigationModel'
import { Shield, Settings as SettingsIcon } from 'lucide-react'
import { getLocalUiRole } from '../lib/api'

export function SupportNavigation({ currentPath }: { currentPath: string }) {
  const localRole = getLocalUiRole()
  const visibleItems = SUPPORT_NAV.filter((item) => item.route !== '/admin' || localRole === 'admin')

  return (
    <nav aria-label="Support" className="space-y-1 support-nav pt-2 mt-2">
      {visibleItems.map((item) => {
        const active = isActive(currentPath, item.route)
        return (
          <Link
            key={item.route}
            to={item.route}
            className={`nav-item ${active ? 'active' : ''}`}
            aria-current={active ? 'page' : undefined}
          >
            {item.route === '/admin' ? <Shield className="h-3.5 w-3.5" /> : <SettingsIcon className="h-3.5 w-3.5" />}
            <span>{item.label}</span>
          </Link>
        )
      })}
    </nav>
  )
}
