/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  configureDailyBrief,
  detectDailyBriefLatest,
  generateDailyBriefSetupInstructions,
  getDailyBriefStatus,
} from '../../lib/api'
import { ErrorState } from '../common/ErrorState'
import { TechnicalDetails } from '../common/TechnicalDetails'

export function DailyBriefSettingsPanel() {
  const [status, setStatus] = useState<any>(null)
  const [enabled, setEnabled] = useState(true)
  const [showOnToday, setShowOnToday] = useState(true)
  const [outputFolder, setOutputFolder] = useState('')
  const [filePattern, setFilePattern] = useState('HB-Daily-Brief-*.md')
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [advanced, setAdvanced] = useState<any>(null)

  function applyStatus(result: any) {
    setStatus(result)
    const config = result?.config || {}
    if (typeof config.enabled === 'boolean') setEnabled(config.enabled)
    if (typeof config.show_on_today === 'boolean') setShowOnToday(config.show_on_today)
    if (config.output_folder != null) setOutputFolder(config.output_folder || '')
    if (config.file_pattern) setFilePattern(config.file_pattern)
  }

  async function refreshStatus() {
    setBusy('status')
    setError(null)
    try {
      const result = await getDailyBriefStatus()
      applyStatus(result)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(null)
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshStatus()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function savePatch(patch: Record<string, unknown>) {
    setBusy('save')
    setError(null)
    try {
      const result = await configureDailyBrief(patch)
      applyStatus(result)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(null)
    }
  }

  async function checkBrief() {
    setBusy('detect')
    setError(null)
    try {
      const result = await detectDailyBriefLatest()
      setAdvanced(result)
      await refreshStatus()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(null)
    }
  }

  async function generateAdvancedSetup() {
    setBusy('instructions')
    setError(null)
    try {
      const result = await generateDailyBriefSetupInstructions({
        output_folder: outputFolder || undefined,
        file_pattern: filePattern,
      })
      setAdvanced(result)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(null)
    }
  }

  const currentState = status?.state || (enabled ? 'configured_waiting' : 'not_configured')

  return (
    <div className="card">
      <h3 className="font-medium mb-2">Daily Brief</h3>
      <div className="text-xs text-[var(--hb-muted)] mb-3">
        Show a prepared daily summary on Today when one is available.
      </div>

      <div className="flex flex-wrap items-center gap-2 mb-3">
        <span className="badge">{dailyBriefLabel(currentState)}</span>
        <button className="badge" onClick={checkBrief} disabled={busy !== null}>
          {busy === 'detect' ? 'Checking...' : "Check for today's brief"}
        </button>
        <Link to="/today" className="badge">Open Today</Link>
      </div>

      <div className="grid gap-3">
        <label className="flex items-center gap-2 text-xs">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(event) => {
              setEnabled(event.target.checked)
              savePatch({ enabled: event.target.checked })
            }}
          />
          Enable Daily Brief
        </label>

        <label className="flex items-center gap-2 text-xs">
          <input
            type="checkbox"
            checked={showOnToday}
            onChange={(event) => {
              setShowOnToday(event.target.checked)
              savePatch({ show_on_today: event.target.checked })
            }}
          />
          Show on Today
        </label>

        <div>
          <label htmlFor="daily-brief-folder" className="text-xs mb-1">Brief folder</label>
          <input
            id="daily-brief-folder"
            className="w-full bg-[var(--hb-bg)] border border-[var(--hb-border)] rounded px-2 py-1 text-sm"
            value={outputFolder}
            onChange={(event) => setOutputFolder(event.target.value)}
            onBlur={() => savePatch({ output_folder: outputFolder })}
            placeholder="Choose the folder where briefs are saved"
          />
        </div>

        <div>
          <label htmlFor="daily-brief-pattern" className="text-xs mb-1">File name pattern</label>
          <input
            id="daily-brief-pattern"
            className="w-full bg-[var(--hb-bg)] border border-[var(--hb-border)] rounded px-2 py-1 text-sm"
            value={filePattern}
            onChange={(event) => setFilePattern(event.target.value)}
            onBlur={() => savePatch({ file_pattern: filePattern })}
          />
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <button className="badge" onClick={refreshStatus} disabled={busy !== null}>
          {busy === 'status' ? 'Checking...' : 'Check status'}
        </button>
        <button className="badge" onClick={generateAdvancedSetup} disabled={busy !== null}>
          {busy === 'instructions' ? 'Preparing...' : 'Advanced setup'}
        </button>
      </div>

      <ErrorState userMessage="Daily Brief settings could not be loaded." error={error} />

      <TechnicalDetails
        summary="Advanced Daily Brief details"
        details={advanced ? safeDetail(advanced) : safeDetail(status)}
        className="mt-3"
      />
    </div>
  )
}

function safeDetail(value: unknown) {
  if (!value) return ''
  if (typeof value !== 'object') return String(value)
  return Object.entries(value as Record<string, unknown>).map(([key, entry]) => {
    if (entry && typeof entry === 'object') return `${key}: ${Object.keys(entry as Record<string, unknown>).join(', ')}`
    return `${key}: ${String(entry)}`
  }).join('\n')
}

function dailyBriefLabel(state: string) {
  if (state === 'brief_available') return 'Brief available'
  if (state === 'brief_stale') return 'Brief needs refresh'
  if (state === 'configured_waiting') return 'Waiting for first update approval'
  if (state === 'not_configured') return 'Not configured'
  if (state === 'markdown_parse_warning') return 'Brief needs review'
  if (state === 'brief_generation_failed') return 'Brief unavailable'
  return 'Status unavailable'
}
