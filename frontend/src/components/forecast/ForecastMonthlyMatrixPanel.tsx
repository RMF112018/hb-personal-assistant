import { useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Maximize2, Minimize2 } from 'lucide-react'

import { api } from '../../lib/api'
import type { MonthlyExportPayload } from './forecastMonthlyExport'
import { ForecastMonthlyExportMenu } from './ForecastMonthlyExportMenu'
import { ForecastMonthlyMatrixTable } from './ForecastMonthlyMatrixTable'
import { ForecastPanel } from './ForecastPrimitives'

// PDF export is gated on a readability proof for wide month windows; until it lands, the menu shows PDF
// as disabled with explanatory copy. CSV and Excel are always available for a ready, non-empty table.
const PDF_ENABLED = false

/**
 * Output-scoped monthly forecast matrix panel. Resolves the active persisted output (the page-owned
 * selection, else the project's latest output) and fetches its table-ready matrix. All values are
 * backend-authoritative; the table only formats / sorts / filters / groups.
 */
export function ForecastMonthlyMatrixPanel({
  project,
  activeOutputId,
}: {
  project: string
  activeOutputId?: string
}) {
  // Resolve the latest output when the page hasn't pinned one (mirrors the sibling panels).
  const { data: outputsResp } = useQuery({
    queryKey: ['forecast', 'db', 'outputs', project],
    queryFn: () => api.getForecastDbOutputs(project),
    enabled: !activeOutputId,
  })
  const outputId = activeOutputId ?? outputsResp?.outputs?.[0]?.output_id

  const {
    data: table,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['forecast', 'db', 'monthly-table', outputId],
    queryFn: () => api.getForecastDbMonthlyTable(outputId as string),
    enabled: Boolean(outputId),
  })

  // Full-screen is a pure presentation toggle. It is intentionally NOT part of any React Query key,
  // so toggling never refetches the matrix.
  const [fullScreen, setFullScreen] = useState(false)

  // Stable bridge the table publishes its current-view export factory into (a ref, so export never lifts
  // table state nor triggers a refetch). Export is offered only for a ready table that has rows.
  const exportPayloadFactoryRef = useRef<(() => MonthlyExportPayload) | null>(null)
  const canExport = table?.status === 'ready' && (table?.rows?.length ?? 0) > 0

  if (!outputId) return null

  return (
    <ForecastPanel
      title="Monthly forecast"
      description="Completed-to-date actuals and forecast-to-complete by budget code and month, with row totals, a total row, and estimated cost at completion. All values are calculated and saved by the application."
      className={fullScreen ? 'forecast-monthly-panel is-fullscreen' : 'forecast-monthly-panel'}
      actions={
        <div className="forecast-panel-actions">
          <ForecastMonthlyExportMenu
            factoryRef={exportPayloadFactoryRef}
            disabled={!canExport}
            pdfEnabled={PDF_ENABLED}
          />
          <button
            type="button"
            className="forecast-btn-ghost"
            aria-pressed={fullScreen}
            onClick={() => setFullScreen((v) => !v)}
          >
            {fullScreen ? <Minimize2 size={14} strokeWidth={2} /> : <Maximize2 size={14} strokeWidth={2} />}
            {fullScreen ? 'Exit full screen' : 'Full screen'}
          </button>
        </div>
      }
    >
      <ForecastMonthlyMatrixTable
        table={table}
        loading={isLoading}
        error={error ? 'Please try again.' : null}
        fullScreen={fullScreen}
        exportPayloadFactoryRef={exportPayloadFactoryRef}
      />
    </ForecastPanel>
  )
}
