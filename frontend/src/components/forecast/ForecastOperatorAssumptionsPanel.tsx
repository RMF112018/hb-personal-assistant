/* Standalone panel wrapper around ForecastAssumptionsSection. The section holds all the
 * query/write/form/table logic; this wrapper only supplies the panel chrome. After the Run Center
 * refactor the section is embedded in the Create Forecast modal, so this panel is no longer rendered
 * as a default page-level panel (kept for any standalone/admin reuse + existing tests). */
import { ClipboardList } from 'lucide-react'

import { ForecastPanel } from './ForecastPrimitives'
import { ForecastAssumptionsSection } from './ForecastAssumptionsSection'

export function ForecastOperatorAssumptionsPanel({ project }: { project: string }) {
  return (
    <ForecastPanel
      icon={ClipboardList}
      title="Forecast Assumptions"
      description="Capture assumptions and required inputs that should be considered before this forecast is submitted."
    >
      <ForecastAssumptionsSection project={project} />
    </ForecastPanel>
  )
}
