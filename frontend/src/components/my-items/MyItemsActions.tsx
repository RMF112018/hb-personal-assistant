import { Link } from 'react-router-dom'

export function MyItemsSettingsLink() {
  return (
    <Link to="/settings" className="badge">
      Open Settings
    </Link>
  )
}

export function MyItemsProjectsLink() {
  return (
    <Link to="/projects" className="badge">
      Open Projects
    </Link>
  )
}

export function MyItemsTodayLink() {
  return (
    <Link to="/today" className="badge">
      Open Today
    </Link>
  )
}
