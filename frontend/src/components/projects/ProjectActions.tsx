import { Link } from 'react-router-dom'

export function ProjectConnectionsLink() {
  return (
    <Link to="/settings" className="badge">
      Review project connections in Settings
    </Link>
  )
}

export function AllProjectsLink({ label = 'Open All Projects' }: { label?: string }) {
  return (
    <Link to="/projects/all" className="badge">
      {label}
    </Link>
  )
}
