import { useState } from 'react'

import type { ForecastGeneratorKind } from '../../lib/api'
import { ForecastErrorCallout } from './ForecastErrorCallout'
import { ForecastActionButton } from './ForecastPageChrome'
import { ForecastPanel } from './ForecastPrimitives'

/**
 * Generation controls for the Forecast Run Center. The primary operator action is DB-native
 * generation (reads the app DB, computes in memory, persists forecast outputs when the write gate is
 * enabled). The legacy package-backed paths — DB-config (live-config snapshot) and file-config — are
 * demoted behind an expandable disclosure for comparison/validation only. The page owns all
 * state/handlers and passes display-ready data down; this component is presentational apart from the
 * local disclosure toggle.
 */
export interface ForecastGeneratePanelProps {
  projectKey: string | null
  selectedBlocked: boolean
  dateError: string | null
  generatorKinds: { value: ForecastGeneratorKind; label: string }[]
  /** DB-native — the production-intended persistence path. Restricted to the comprehensive kind. */
  primary: {
    onGenerate: () => void
    generating: boolean
    error: string | null
    errorActionTo: string | null
    /** Extra disable signal (e.g. an invalid/incomplete operator month window). */
    disabled?: boolean
  }
  /** Legacy package-backed DB-config (live-config snapshot) path. Keeps the generator-kind selector. */
  legacyDbConfig: {
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
  /** Legacy package-backed file-config path. */
  legacyFile: {
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
  legacyDbConfig,
  legacyFile,
}: ForecastGeneratePanelProps) {
  const [showLegacy, setShowLegacy] = useState(false)

  const noProject = !projectKey
  const primaryDisabled = primary.generating || noProject || selectedBlocked || Boolean(primary.disabled)
  const dbConfigDisabled =
    legacyDbConfig.generating || legacyDbConfig.notReady || noProject || selectedBlocked
  const fileDisabled = legacyFile.generating || noProject || selectedBlocked

  return (
    <ForecastPanel
      title="Generate forecast"
      description="Generates the selected project's forecast directly from the local database and saves it as a forecast output (when output writes are enabled). Procore and live project data are never modified. If a run can't complete in this environment, it's reported below as a failed request."
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-[var(--hb-muted)]">Type</span>
        <select
          id="db-native-kind"
          aria-label="Forecast type"
          value="comprehensive"
          disabled
          className="rounded border border-[var(--hb-border)] bg-transparent px-2 py-1.5 text-sm opacity-70"
        >
          <option value="comprehensive">Comprehensive</option>
        </select>
        <ForecastActionButton onClick={primary.onGenerate} disabled={primaryDisabled}>
          {primary.generating ? 'Generating…' : 'Generate forecast'}
        </ForecastActionButton>
      </div>
      <p className="text-xs text-[var(--hb-muted)] mt-1">
        Additional forecast types aren't available yet on this path.
      </p>

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
          Advanced / legacy package-backed generation
        </button>
        {showLegacy && (
          <div className="mt-3 space-y-4">
            <p className="text-sm text-[var(--hb-muted)]">
              These are legacy package-backed paths, kept for comparison and validation. They are not
              the primary DB-native operator path.
            </p>

            {/* Legacy DB-config (live-config snapshot) — retains the generator-kind selector. */}
            <div>
              <p className="text-sm font-medium">Generate from DB config (legacy package path)</p>
              <div className="flex flex-wrap items-center gap-2 mt-2">
                <label htmlFor="db-config-kind" className="text-sm text-[var(--hb-muted)]">
                  Type
                </label>
                <select
                  id="db-config-kind"
                  aria-label="Legacy DB-config forecast type"
                  value={legacyDbConfig.genKind}
                  onChange={(e) =>
                    legacyDbConfig.onKindChange(e.target.value as ForecastGeneratorKind)
                  }
                  disabled={legacyDbConfig.generating || legacyDbConfig.notReady}
                  className="rounded border border-[var(--hb-border)] bg-transparent px-2 py-1.5 text-sm disabled:opacity-50"
                >
                  {generatorKinds.map((k) => (
                    <option key={k.value} value={k.value}>
                      {k.label}
                    </option>
                  ))}
                </select>
                <ForecastActionButton
                  variant="ghost"
                  onClick={legacyDbConfig.onGenerate}
                  disabled={dbConfigDisabled}
                >
                  {legacyDbConfig.generating ? 'Generating…' : 'Generate from DB config'}
                </ForecastActionButton>
              </div>
              {legacyDbConfig.notReady && (
                <ForecastErrorCallout
                  tone="error"
                  lines={
                    legacyDbConfig.blockerReasons.length > 0
                      ? legacyDbConfig.blockerReasons
                      : ['Generation from live configuration is not available yet.']
                  }
                  actions={legacyDbConfig.blockerActions.map((a) => ({
                    label: a.label,
                    to: a.to ?? undefined,
                  }))}
                />
              )}
              {!legacyDbConfig.notReady && legacyDbConfig.warnings.length > 0 && (
                <ForecastErrorCallout tone="warning" lines={legacyDbConfig.warnings} />
              )}
              {legacyDbConfig.error && (
                <ForecastErrorCallout
                  tone="error"
                  lines={[legacyDbConfig.error]}
                  actions={
                    legacyDbConfig.errorActionTo
                      ? [{ label: 'Open storage settings', to: legacyDbConfig.errorActionTo }]
                      : []
                  }
                />
              )}
            </div>

            {/* Legacy file-config. */}
            <div>
              <p className="text-sm font-medium">Generate from file config (legacy package path)</p>
              <div className="mt-2">
                <ForecastActionButton
                  variant="ghost"
                  onClick={legacyFile.onGenerate}
                  disabled={fileDisabled}
                >
                  {legacyFile.generating ? 'Generating…' : 'Generate from file config'}
                </ForecastActionButton>
              </div>
              {legacyFile.error && (
                <ForecastErrorCallout
                  tone="error"
                  lines={[legacyFile.error]}
                  actions={
                    legacyFile.errorActionTo
                      ? [{ label: 'Open storage settings', to: legacyFile.errorActionTo }]
                      : []
                  }
                />
              )}
            </div>
          </div>
        )}
      </div>
    </ForecastPanel>
  )
}
