import { useEffect, useRef, useState, type MutableRefObject } from 'react'
import { Download } from 'lucide-react'

import type { MonthlyExportPayload } from './forecastMonthlyExport'
import { exportCsv, exportXlsx } from './forecastMonthlyExportWriters'

const ERROR_COPY = 'The export could not be created. Please try again.'
const PDF_DEFERRED_COPY =
  'PDF export is not available for wide monthly forecasts yet. Export Excel for the full detail.'

/**
 * Export control for the Monthly Forecast panel header. It pulls the current visible table view on
 * demand via a stable factory ref (never lifting TanStack state and never re-fetching), then hands the
 * payload to a writer. CSV is synchronous; Excel is a dynamically-imported writer. PDF is shown disabled
 * with explanatory copy unless enabled.
 */
type ExportWriter = (payload: MonthlyExportPayload) => void | Promise<void>

export function ForecastMonthlyExportMenu({
  factoryRef,
  disabled,
  pdfEnabled = false,
  onExportPdf,
}: {
  factoryRef: MutableRefObject<(() => MonthlyExportPayload) | null>
  disabled: boolean
  pdfEnabled?: boolean
  // Wired only once the wide-window PDF readability proof lands; absent today, so PDF stays deferred.
  onExportPdf?: ExportWriter
}) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onPointerDown = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false)
    }
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  const runExport = async (writer: ExportWriter) => {
    setError(null)
    const payload = factoryRef.current?.()
    if (!payload) {
      setError(ERROR_COPY)
      return
    }
    try {
      setBusy(true)
      await writer(payload)
      setOpen(false)
    } catch {
      setError(ERROR_COPY)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="forecast-export-menu" ref={containerRef}>
      <button
        type="button"
        className="forecast-btn-ghost"
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={disabled}
        onClick={() => {
          setError(null)
          setOpen((v) => !v)
        }}
      >
        <Download size={14} strokeWidth={2} />
        Export
      </button>

      {open && (
        <div className="forecast-export-dropdown" role="menu" aria-label="Export the monthly forecast">
          <button
            type="button"
            role="menuitem"
            className="forecast-export-item"
            disabled={busy}
            onClick={() => void runExport(exportCsv)}
          >
            CSV
          </button>
          <button
            type="button"
            role="menuitem"
            className="forecast-export-item"
            disabled={busy}
            onClick={() => void runExport(exportXlsx)}
          >
            Excel
          </button>
          {/* PDF is gated on a wide-month-window readability proof. Until that lands (and a PDF writer
              is wired), pdfEnabled stays false and the item is shown disabled with explanatory copy. */}
          {pdfEnabled && onExportPdf ? (
            <button
              type="button"
              role="menuitem"
              className="forecast-export-item"
              disabled={busy}
              onClick={() => void runExport(onExportPdf)}
            >
              PDF
            </button>
          ) : (
            <div className="forecast-export-item is-disabled" aria-disabled role="menuitem">
              <span>PDF</span>
              <span className="forecast-export-note">{PDF_DEFERRED_COPY}</span>
            </div>
          )}
          {error && <p className="forecast-export-error">{error}</p>}
        </div>
      )}
    </div>
  )
}
