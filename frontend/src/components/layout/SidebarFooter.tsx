import { DataQualityIndicator } from './DataQualityIndicator'
import { SupportNavigation } from '../../layouts/SupportNavigation'
import { getLocalUiRole } from '../../lib/api'

export function SidebarFooter({ currentPath }: { currentPath: string }) {
  const localRole = getLocalUiRole()
  return (
    <div className="mt-auto shrink-0 border-t border-[var(--hb-border)] pt-3">
      {localRole !== 'admin' && <DataQualityIndicator />}
      <SupportNavigation currentPath={currentPath} />
    </div>
  )
}
