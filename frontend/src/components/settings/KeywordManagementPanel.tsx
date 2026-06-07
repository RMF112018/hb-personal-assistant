/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState } from 'react'

import {
  addProjectKeyword,
  explainProjectKeywordMatch,
  getProjectKeywords,
} from '../../lib/api'
import { safeDisplayText } from '../../lib/errorCopy'
import { ErrorState } from '../common/ErrorState'
import { EmptyState } from '../common/EmptyState'
import { TechnicalDetails } from '../common/TechnicalDetails'

export function KeywordManagementPanel() {
  const [project, setProject] = useState('')
  const [term, setTerm] = useState('')
  const [keywords, setKeywords] = useState<any>(null)
  const [explain, setExplain] = useState<any>(null)
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState<string | null>(null)

  async function refreshKeywords() {
    if (!project.trim()) return
    setBusy('refresh')
    setError(null)
    try {
      setKeywords(await getProjectKeywords(project.trim()))
    } catch (err) {
      setError(err)
    } finally {
      setBusy(null)
    }
  }

  async function addKeyword() {
    if (!project.trim() || !term.trim()) return
    setBusy('add')
    setError(null)
    try {
      await addProjectKeyword(project.trim(), term.trim(), 1)
      setTerm('')
      setKeywords(await getProjectKeywords(project.trim()))
    } catch (err) {
      setError(err)
    } finally {
      setBusy(null)
    }
  }

  async function explainKeyword() {
    if (!project.trim() || !term.trim()) return
    setBusy('explain')
    setError(null)
    try {
      setExplain(await explainProjectKeywordMatch(project.trim(), term.trim()))
    } catch (err) {
      setError(err)
    } finally {
      setBusy(null)
    }
  }

  const rows = keywordRows(keywords)

  return (
    <div className="card">
      <h3 className="font-medium mb-2">Project Keywords</h3>
      <div className="text-xs text-[var(--hb-muted)] mb-3">
        Add business terms that help match project information.
      </div>

      <div className="grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <label htmlFor="keyword-project" className="text-xs mb-1">Project</label>
          <input
            id="keyword-project"
            className="w-full bg-[var(--hb-bg)] border border-[var(--hb-border)] rounded px-2 py-1 text-sm"
            value={project}
            onChange={(event) => setProject(event.target.value)}
            placeholder="Project name"
          />
        </div>
        <div>
          <label htmlFor="keyword-term" className="text-xs mb-1">Keyword</label>
          <input
            id="keyword-term"
            className="w-full bg-[var(--hb-bg)] border border-[var(--hb-border)] rounded px-2 py-1 text-sm"
            value={term}
            onChange={(event) => setTerm(event.target.value)}
            placeholder="Keyword or phrase"
          />
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <button className="badge" onClick={addKeyword} disabled={busy !== null || !project || !term}>
          {busy === 'add' ? 'Adding...' : 'Add keyword'}
        </button>
        <button className="badge" onClick={refreshKeywords} disabled={busy !== null || !project}>
          {busy === 'refresh' ? 'Refreshing...' : 'Refresh keywords'}
        </button>
        <button className="badge" onClick={explainKeyword} disabled={busy !== null || !project || !term}>
          {busy === 'explain' ? 'Checking...' : 'Explain match'}
        </button>
      </div>

      <ErrorState userMessage="Project keywords could not be loaded." error={error} />

      <div className="mt-3">
        {rows.length > 0 ? (
          <ul className="space-y-2 text-sm">
            {rows.slice(0, 8).map((row, index) => (
              <li key={index} className="rounded-md border border-[var(--hb-border)] bg-[var(--hb-bg)] px-3 py-2">
                {safeDisplayText(row)}
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState title="No keywords loaded." hint="Choose a project and refresh keywords." />
        )}
      </div>

      {explain && (
        <div className="mt-3 text-sm">
          <div className="font-medium">Match explanation</div>
          <div className="text-[var(--hb-muted)]">{safeDisplayText(explain)}</div>
          <TechnicalDetails summary="Advanced match details" details={safeDetail(explain)} className="mt-2" />
        </div>
      )}
    </div>
  )
}

function keywordRows(value: any): any[] {
  if (Array.isArray(value?.keywords)) return value.keywords
  if (Array.isArray(value?.items)) return value.items
  if (Array.isArray(value)) return value
  return []
}

function safeDetail(value: unknown) {
  if (!value) return ''
  if (typeof value !== 'object') return String(value)
  return Object.entries(value as Record<string, unknown>).map(([key, entry]) => {
    if (entry && typeof entry === 'object') return `${key}: ${Object.keys(entry as Record<string, unknown>).join(', ')}`
    return `${key}: ${String(entry)}`
  }).join('\n')
}
