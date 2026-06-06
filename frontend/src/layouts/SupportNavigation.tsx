import { Link } from 'react-router-dom'
import { SUPPORT_NAV, DISABLED_NAV, isActive } from '../navigation/navigationModel'
import { Shield, Settings as SettingsIcon, MessageCircleOff } from 'lucide-react'

export function SupportNavigation({ currentPath }: { currentPath: string }) {
  return (
    <nav aria-label="Support" className="space-y-1 support-nav border-t border-[var(--hb-border)] pt-3 mt-2">
      {SUPPORT_NAV.map((item) => {
        const active = isActive(currentPath, item.route)
        return (
          <Link
            key={item.route}
            to={item.route}
            className={`nav-item ${active ? 'active' : ''}`}
            aria-current={active ? 'page' : undefined}
          >
            {item.label === 'Admin / Data Confidence' ? <Shield className="h-3.5 w-3.5" /> : <SettingsIcon className="h-3.5 w-3.5" />}
            <span>{item.label}</span>
          </Link>
        )
      })}

      {/* Chat is explicitly disabled - no active route or nav item per spec */}
      {DISABLED_NAV.map((item) => (
        <div
          key={item.route}
          className="nav-item disabled flex items-center gap-2 opacity-40"
          title={item.title}
          aria-disabled="true"
        >
          <MessageCircleOff className="h-3.5 w-3.5" />
          <span>{item.label}</span>
          <span className="ml-auto text-[9px]">(disabled)</span>
        </div>
      ))}
    </nav>
  )
}
