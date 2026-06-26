/* Forecast history modal — one reconciled surface opened from Forecast Context. Saved forecast
 * outputs are selectable (they update the active output); generation requests are informational with
 * honest status, and failed/rejected requests are never shown as saved outputs. Frontend-only
 * reconciliation from data already fetched by the page. */
import { ForecastDialog } from './ForecastDialog'
import { ForecastTable, ForecastTd, ForecastTh } from './ForecastPrimitives'
import { ForecastStatusPill } from './ForecastStatusPill'
import { EmptyState } from '../ui/EmptyState'
import { failureCodeCopy } from './forecastRuntimeCopy'
import type { ForecastDbOutputSummary, ForecastGenerationRequest } from '../../lib/api'

function requestStatusPill(status: string): string {
  if (status === 'completed' || status === 'succeeded' || status === 'generated') return 'validated'
  if (status === 'rejected') return 'rejected'
  if (status === 'failed') return 'failed'
  return 'attention'
}

export interface ForecastHistoryModalProps {
  open: boolean
  onClose: () => void
  outputs: ForecastDbOutputSummary[]
  requests: ForecastGenerationRequest[]
  activeOutputId?: string
  onSelectOutput: (outputId: string) => void
}

export function ForecastHistoryModal({
  open,
  onClose,
  outputs,
  requests,
  activeOutputId,
  onSelectOutput,
}: ForecastHistoryModalProps) {
  const effectiveActiveId = activeOutputId ?? outputs[0]?.output_id

  return (
    <ForecastDialog
      open={open}
      onClose={onClose}
      title="Forecast history"
      description="Saved forecasts you can view, plus the generation requests recorded for this project."
    >
      <h3 className="forecast-section-label">Saved forecasts · {outputs.length}</h3>
      {outputs.length === 0 ? (
        <EmptyState
          title="No saved forecasts yet"
          hint="Submit a forecast from Create Forecast to save one here."
        />
      ) : (
        <ForecastTable
          headers={
            <>
              <ForecastTh>Forecast</ForecastTh>
              <ForecastTh>Saved</ForecastTh>
              <ForecastTh>Estimated final cost</ForecastTh>
              <ForecastTh />
            </>
          }
        >
          {outputs.map((o) => {
            const isActive = o.output_id === effectiveActiveId
            return (
              <tr key={o.output_id}>
                <ForecastTd>Saved forecast output</ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">{o.created_display ?? '—'}</ForecastTd>
                <ForecastTd className="tabular-nums">{o.estimated_final_cost ?? '—'}</ForecastTd>
                <ForecastTd>
                  <button
                    type="button"
                    className="text-sm text-[var(--hb-accent)] disabled:opacity-50"
                    disabled={isActive}
                    onClick={() => {
                      onSelectOutput(o.output_id)
                      onClose()
                    }}
                  >
                    {isActive ? 'Viewing' : 'View'}
                  </button>
                </ForecastTd>
              </tr>
            )
          })}
        </ForecastTable>
      )}

      <h3 className="forecast-section-label mt-6">Generation requests · {requests.length}</h3>
      {requests.length === 0 ? (
        <p className="text-sm text-[var(--hb-muted)] mt-2">No generation requests recorded yet.</p>
      ) : (
        <ForecastTable
          headers={
            <>
              <ForecastTh>Request</ForecastTh>
              <ForecastTh>Window</ForecastTh>
              <ForecastTh>Status</ForecastTh>
              <ForecastTh>Requested</ForecastTh>
            </>
          }
        >
          {requests.map((r) => {
            const failed = r.request_status === 'failed' || r.request_status === 'rejected'
            const failureCopy = failed ? r.failure_message || failureCodeCopy(r.failure_code) : null
            return (
              <tr key={r.request_id}>
                <ForecastTd className="text-[var(--hb-muted)]">
                  {r.request_status === 'completed'
                    ? 'Completed request'
                    : failed
                      ? 'Forecast request'
                      : 'Forecast request'}
                </ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">
                  {r.forecast_start_date || '—'} → {r.forecast_cutoff_date || '—'}
                </ForecastTd>
                <ForecastTd>
                  <ForecastStatusPill status={requestStatusPill(r.request_status)} />
                  {failureCopy && (
                    <p className="mt-1 text-xs text-[var(--hb-muted)]">{failureCopy}</p>
                  )}
                </ForecastTd>
                <ForecastTd className="text-[var(--hb-muted)]">{r.created_utc || '—'}</ForecastTd>
              </tr>
            )
          })}
        </ForecastTable>
      )}
    </ForecastDialog>
  )
}
