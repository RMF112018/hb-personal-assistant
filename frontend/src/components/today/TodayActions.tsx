import { Link } from 'react-router-dom'

export function CheckDataHealthLink() {
  return (
    <Link to="/admin" className="badge">
      Check Data Health
    </Link>
  )
}

export function SettingsLink({ label = 'Open Settings' }: { label?: string }) {
  return (
    <Link to="/settings" className="badge">
      {label}
    </Link>
  )
}
