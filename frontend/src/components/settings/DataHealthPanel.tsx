import { Link } from 'react-router-dom'
import { useState } from 'react'

import { useDataQualitySummary } from '../../hooks/useDataQualitySummary'
import { getDataQualityDetail } from '../../lib/api'
import { getDataQualityCopy } from '../../lib/statusCopy'
import { ErrorState } from '../common/ErrorState'
import { TechnicalDetails } from '../common/TechnicalDetails'

export function DataHealthPanel() {
  const { data, error, refetch, isFetching } = useDataQualitySummary()
  const [detail, setDetail] = useState<unknown>(null)
  const [detailError, setDetailError] = useState<unknown>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const copy = getDataQualityCopy(data?.status)

  async function loadDetail() {
    setLoadingDetail(true)
    setDetailError(null)
    try {
      setDetail(await getDataQualityDetail())
    } catch (err) {
      setDetailError(err)
    } finally {
      setLoadingDetail(false)
    }
  }

  return (
    <div className="card">
      <h3 className="font-medium mb-2">Data Health</h3>
      <div className="flex flex-wrap items-center gap-2">
        <span className="badge">{copy.label}</span>
        <button className="badge" onClick={() => refetch()} disabled={isFetching}>
          {isFetching ? 'Checking...' : 'Open Data Health'}
        </button>
        <Link to="/admin" className="badge">Open Data Health</Link>
      </div>
      <div className="mt-2 text-xs text-[var(--hb-muted)]">
        {data?.message || copy.description}
      </div>

      <ErrorState userMessage="Data Health could not be loaded." error={error} />

      {data?.admin_detail_available && (
        <div className="mt-3">
          <button className="badge" onClick={loadDetail} disabled={loadingDetail}>
            {loadingDetail ? 'Checking...' : 'Check admin details'}
          </button>
          <ErrorState userMessage="Data Health details are not available for this role." error={detailError} />
          <TechnicalDetails
            summary="Advanced Data Health details"
            details={detail ? safeDetail(detail) : ''}
            className="mt-2"
          />
        </div>
      )}
    </div>
  )
}

function safeDetail(value: unknown) {
  if (!value) return ''
  if (typeof value !== 'object') return String(value)
  return Object.entries(value as Record<string, unknown>).map(([key, entry]) => {
    if (Array.isArray(entry)) return `${key}: ${entry.length} items`
    if (entry && typeof entry === 'object') return `${key}: ${Object.keys(entry as Record<string, unknown>).join(', ')}`
    return `${key}: ${String(entry)}`
  }).join('\n')
}
