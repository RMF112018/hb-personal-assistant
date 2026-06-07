import { EmptyState } from '../common/EmptyState'
import { ProjectConnectionsLink } from './ProjectActions'

export function ProjectSetupState() {
  return (
    <EmptyState
      title="No active projects are connected yet."
      hint="Project data will appear after sources are connected and approved."
      actions={<ProjectConnectionsLink />}
    />
  )
}
