import { useEffect, useId } from 'react'
import type { ReactNode } from 'react'
import { X } from 'lucide-react'

import './forecast-ui.css'

export interface ForecastDialogProps {
  open: boolean
  onClose: () => void
  title: string
  /** Optional explicit id for the title element (defaults to a generated id). */
  titleId?: string
  description?: string
  descriptionId?: string
  /** Footer content (typically Cancel / Submit actions). */
  footer?: ReactNode
  children: ReactNode
}

/**
 * Reusable forecast modal. Renders nothing when closed. Closes on Escape, backdrop
 * click, and the header close button; clicks inside the dialog do not close it.
 * Rendered inline at the page root with fixed positioning (no portal dependency).
 */
export function ForecastDialog({
  open,
  onClose,
  title,
  titleId,
  description,
  descriptionId,
  footer,
  children,
}: ForecastDialogProps) {
  const generatedTitleId = useId()
  const generatedDescId = useId()
  const resolvedTitleId = titleId ?? generatedTitleId
  const resolvedDescId = description ? (descriptionId ?? generatedDescId) : undefined

  useEffect(() => {
    if (!open) return
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.stopPropagation()
        onClose()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="forecast-dialog-backdrop" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={resolvedTitleId}
        aria-describedby={resolvedDescId}
        className="forecast-dialog"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="forecast-dialog-header">
          <div className="min-w-0">
            <h2 id={resolvedTitleId} className="forecast-section-label">
              {title}
            </h2>
            {description && (
              <p id={resolvedDescId} className="text-sm text-[var(--hb-muted)] mt-1 leading-relaxed">
                {description}
              </p>
            )}
          </div>
          <button
            type="button"
            className="forecast-dialog-close"
            onClick={onClose}
            aria-label="Close"
          >
            <X size={16} strokeWidth={2} />
          </button>
        </div>
        <div className="forecast-dialog-body">{children}</div>
        {footer && <div className="forecast-dialog-footer">{footer}</div>}
      </div>
    </div>
  )
}
