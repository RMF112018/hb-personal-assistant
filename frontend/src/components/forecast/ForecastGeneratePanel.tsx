import { useState } from 'react'

import type { ForecastGeneratorKind } from '../../lib/api'
import { ForecastErrorCallout } from './ForecastErrorCallout'
import { ForecastActionButton } from './ForecastPageChrome'
import { ForecastPanel } from './ForecastPrimitives'

/**
 * Generation controls for the Forecast Run Center. DB-backed generation is the primary operator
 * action; the legacy file-configuration path is demoted behind an expandable disclosure. The page
 * owns all state/handlers and passes display-ready data down — this component is presentational
 * apart from the local disclosure toggle.
 */
export interface ForecastGeneratePanelProps {
  projectKey: string | null
  selectedBlocked: boolean
  dateError: string | null
  generatorKinds: { value: ForecastGeneratorKind; label: string }[]
  primary: {
    genKind: ForecastGeneratorKind
    onKindChange: (k: ForecastGeneratorKind) => void
    onGenerate: () => void
    generating: boolean
    notReady: boolean
    blockerReasons: string[]
    blockerActions: { label: string; to: string | null }[]
    warnings: string[]
    error: string | null
    errorActionTo: string | null
  }
  legacy: {
    onGenerate: () => void
    generating: boolean
    error: string | null
    errorActionTo: string | null
  }
}

export function ForecastGeneratePanel({
  projectKey,
  selectedBlocked,
  dateError,
  generatorKinds,
  primary,
  legacy,
}: ForecastGeneratePanelProps) {
  const [showLegacy, setShowLegacy] = useState(false)

  const noProject = !projectKey
  const primaryDisabled = primary.generating || primary.notReady || noProject || selectedBlocked
  const legacyDisabled = legacy.generating || noProject || selectedBlocked

  return (
    <ForecastPanel
      title="Generate forecast"
      description="Generates the selected project's forecast from the promoted live configuration. Procore and live project data are never modified, and no download/export package is produced here. If a run can't complete in this environment, it's reported below as a failed request."
    >
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor="db-config-kind" className="text-sm text-[var(--hb-muted)]">
          Type
        </label>
        <select
          id="db-config-kind"
          aria-label="Forecast type"
          value={primary.genKind}
          onChange={(e) => primary.onKindChange(e.target.value as ForecastGeneratorKind)}
          disabled={primary.generating || primary.notReady}
          className="rounded border border-[var(--hb-border)] bg-transparent px-2 py-1.5 text-sm disabled:opacity-50"
        >
          {generatorKinds.map((k) => (
            <option key={k.value} value={k.value}>
              {k.label}
            </option>
          ))}
        </select>
        <ForecastActionButton onClick={primary.onGenerate} disabled={primaryDisabled}>
          {primary.generating ? 'Generating…' : 'Generate DB-backed forecast'}
        </ForecastActionButton>
      </div>

      {primary.notReady && (
        <ForecastErrorCallout
          tone="error"
          lines={
            primary.blockerReasons.length > 0
              ? primary.blockerReasons
              : ['Generation from live configuration is not available yet.']
          }
          actions={primary.blockerActions.map((a) => ({ label: a.label, to: a.to ?? undefined }))}
        />
      )}
      {!primary.notReady && primary.warnings.length > 0 && (
        <ForecastErrorCallout tone="warning" lines={primary.warnings} />
      )}
      {primary.error && (
        <ForecastErrorCallout
          tone="error"
          lines={[primary.error]}
          actions={
            primary.errorActionTo
              ? [{ label: 'Open storage settings', to: primary.errorActionTo }]
              : []
          }
        />
      )}
      {dateError && (
        <p className="text-sm text-rose-300 mt-2" role="status">
          {dateError}
        </p>
      )}

      <div className="mt-4 border-t border-[var(--hb-border)] pt-3">
        <button
          type="button"
          onClick={() => setShowLegacy((v) => !v)}
          aria-expanded={showLegacy}
          className="text-sm text-[var(--hb-muted)] hover:text-[var(--hb-fg,inherit)] inline-flex items-center gap-1"
        >
          <span aria-hidden>{showLegacy ? '▾' : '▸'}</span>
          Advanced / legacy file-configuration generation
        </button>
        {showLegacy && (
          <div className="mt-3">
            <p className="text-sm text-[var(--hb-muted)]">
              This is not the DB-backed operator path. It writes a file-configuration forecast and is
              kept for backward compatibility.
            </p>
            <div className="mt-2">
              <ForecastActionButton
                variant="ghost"
                onClick={legacy.onGenerate}
                disabled={legacyDisabled}
              >
                {legacy.generating ? 'Generating…' : 'Generate file-config forecast'}
              </ForecastActionButton>
            </div>
            {legacy.error && (
              <ForecastErrorCallout
                tone="error"
                lines={[legacy.error]}
                actions={
                  legacy.errorActionTo
                    ? [{ label: 'Open storage settings', to: legacy.errorActionTo }]
                    : []
                }
              />
            )}
          </div>
        )}
      </div>
    </ForecastPanel>
  )
}
