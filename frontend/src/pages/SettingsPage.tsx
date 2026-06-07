import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTheme } from '../app/providers'
import { DailyBriefRenderer } from '../components/daily-brief/DailyBriefRenderer'
import { ErrorState } from '../components/ui/ErrorState'
/* eslint-disable @typescript-eslint/no-explicit-any */
import {
  getDailyBriefStatus,
  configureDailyBrief,
  generateDailyBriefSetupInstructions,
  validateDailyBriefOutputFolder,
  detectDailyBriefLatest,
  // Prompt 14B / 14C / E (accounts + project connections now via reusable panels; see Prompt D/E)
  getSettingsSources,
  getSettingsKeywords,
  getProjectKeywords,
  addProjectKeyword,
  explainProjectKeywordMatch,
  getSettingsDailyBrief,
  getSettingsPreferences,
  getSettingsAdminSync,
  patchSettingsPreferences,
  patchSettingsAdmin,
} from '../lib/api'
import { AccountConnectionsPanel } from '../components/settings/AccountConnectionsPanel'
import { ProjectConnectionsPanel } from '../components/settings/ProjectConnectionsPanel'

// Settings (Prompt 20 polish): guided local-first onboarding and preferences.
// Sections: Account Connections, Project Connections, Daily Brief (external AI writes the .md; this app only detects/presents),
// Preferences (real local persist), Admin (role-gated).
// No raw panels, no alerts, no "stub" in normal UI, no live sync from preview/save flows. CM-first labels and clear next actions.

export function SettingsPage() {
  const { theme, setTheme } = useTheme()
  const [status, setStatus] = useState<any>(null)
  const [loadingStatus, setLoadingStatus] = useState(false)

  // Wizard form state (local; persisted via backend configure)
  const [enabled, setEnabled] = useState(true)
  const [platform, setPlatform] = useState<'claude' | 'chatgpt' | 'perplexity' | 'other'>('claude')
  const [outputFolder, setOutputFolder] = useState('')
  const [filePattern, setFilePattern] = useState('HB-Daily-Brief-*.md')
  const [staleMinutes, setStaleMinutes] = useState(1440)
  const [showOnToday, setShowOnToday] = useState(true)

  const [instrResult, setInstrResult] = useState<any>(null)
  const [validateResult, setValidateResult] = useState<any>(null)
  const [detectResult, setDetectResult] = useState<any>(null)
  const [busy, setBusy] = useState<string | null>(null)

  // Prompt 14C/20/E: debug "Load" panels and alerts removed (FPR-004); use status + guided actions only.
  // Account connections (Prompt D) and Project Connections (Prompt E) now rendered via reusable panels — no per-section raw result state for these.
  const [sourcesResult, setSourcesResult] = useState<any>(null)
  const [sourcesError, setSourcesError] = useState<string | null>(null)
  const [keywordsResult, setKeywordsResult] = useState<any>(null)
  const [keywordsError, setKeywordsError] = useState<string | null>(null)
  const [dailyBriefResult, setDailyBriefResult] = useState<any>(null)
  const [dailyBriefError, setDailyBriefError] = useState<string | null>(null)
  const [prefsResult, setPrefsResult] = useState<any>(null)
  const [prefsError, setPrefsError] = useState<string | null>(null)
  const [adminSyncResult, setAdminSyncResult] = useState<any>(null)
  const [adminSyncError, setAdminSyncError] = useState<string | null>(null)
  const [adminPatchMsg, setAdminPatchMsg] = useState<string | null>(null)
  const [prefsPatchMsg, setPrefsPatchMsg] = useState<string | null>(null)
  // Prompt 20 keyword management state (FPR-017)
  const [kwProject, setKwProject] = useState('')
  const [kwTerm, setKwTerm] = useState('')
  const [kwList, setKwList] = useState<any>(null)
  const [kwExplain, setKwExplain] = useState<any>(null)

  async function refreshStatus() {
    setLoadingStatus(true)
    try {
      const s = await getDailyBriefStatus()
      setStatus(s)
      // Seed form from current config if present
      const c = s?.config || s?.config || {}
      if (typeof c.enabled === 'boolean') setEnabled(c.enabled)
      if (c.platform) setPlatform(c.platform)
      if (c.output_folder) setOutputFolder(c.output_folder)
      if (c.file_pattern) setFilePattern(c.file_pattern)
      if (c.stale_threshold_minutes) setStaleMinutes(c.stale_threshold_minutes)
      if (typeof c.show_on_today === 'boolean') setShowOnToday(c.show_on_today)
    } catch {
      // keep prior; UI will show advisory
    } finally {
      setLoadingStatus(false)
    }
  }

  useEffect(() => {
    // initial load; config may change via other actions so we refresh explicitly on button
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshStatus()
  }, [])

  async function doConfigure(patch: any) {
    setBusy('configure')
    try {
      const updated = await configureDailyBrief(patch)
      setStatus(updated)
      // Re-seed from response
      const c = updated?.config || {}
      if (typeof c.enabled === 'boolean') setEnabled(c.enabled)
      if (c.platform) setPlatform(c.platform)
      if (c.output_folder != null) setOutputFolder(c.output_folder || '')
      if (c.file_pattern) setFilePattern(c.file_pattern)
      if (c.stale_threshold_minutes) setStaleMinutes(c.stale_threshold_minutes)
      if (typeof c.show_on_today === 'boolean') setShowOnToday(c.show_on_today)
    } catch {
      // alert removed per FPR-004 (raw/debug cleanup)
    } finally {
      setBusy(null)
    }
  }

  async function onToggleEnabled(next: boolean) {
    setEnabled(next)
    await doConfigure({ enabled: next })
  }

  async function onPlatformChange(next: 'claude' | 'chatgpt' | 'perplexity' | 'other') {
    setPlatform(next)
    await doConfigure({ platform: next })
  }

  async function onFolderBlur() {
    if (outputFolder && outputFolder !== (status?.config?.output_folder || '')) {
      await doConfigure({ output_folder: outputFolder })
    }
  }

  async function onPatternBlur() {
    await doConfigure({ file_pattern: filePattern })
  }

  async function onStaleBlur() {
    await doConfigure({ stale_threshold_minutes: staleMinutes })
  }

  async function onShowToggle(next: boolean) {
    setShowOnToday(next)
    await doConfigure({ show_on_today: next })
  }

  async function generateInstructions() {
    setBusy('instructions')
    setInstrResult(null)
    try {
      const res = await generateDailyBriefSetupInstructions({
        platform,
        output_folder: outputFolder || undefined,
        file_pattern: filePattern,
      })
      setInstrResult(res)
    } catch {
      // alert removed per FPR-004 (raw/debug cleanup)
    } finally {
      setBusy(null)
    }
  }

  async function validateFolder() {
    setBusy('validate')
    setValidateResult(null)
    try {
      const res = await validateDailyBriefOutputFolder({ folder: outputFolder || undefined })
      setValidateResult(res)
    } catch {
      // alert removed (FPR-004); errors are non-blocking for this flow
    } finally {
      setBusy(null)
    }
  }

  async function testDetection() {
    setBusy('detect')
    setDetectResult(null)
    try {
      const res = await detectDailyBriefLatest()
      setDetectResult(res)
      // Also refresh main status
      await refreshStatus()
    } catch {
      // alert removed (FPR-004); errors are non-blocking for this flow
    } finally {
      setBusy(null)
    }
  }

  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      // ignore
    }
  }

  // Prompt 20 / FPR-005: explicit precedence + helper (disabled -> not_configured; else prefer detect then status)
  function computeDailyBriefState(detect: any, st: any): string | undefined {
    if (st?.config?.enabled === false) return 'not_configured';
    return detect?.state ?? st?.state;
  }
  const currentState = computeDailyBriefState(detectResult, status);
  const previewPath = detectResult?.last_file?.path || status?.last_file?.path || status?.config?.output_folder
  const previewGenerated = detectResult?.last_file?.mtime_utc || status?.last_file?.mtime_utc
  const previewWarnings = detectResult?.parse_warnings || status?.parse_warnings || []
  const previewContent = detectResult?.content || detectResult?.markdown

  return (
    <div className="max-w-2xl space-y-4 text-sm">
      <div className="card">
        <div className="font-medium mb-2">Appearance</div>
        <div className="flex gap-2">
          {(['dark', 'light', 'system'] as const).map((t) => (
            <button key={t} className={`badge ${theme === t ? 'ring-1 ring-[var(--hb-accent)]' : ''}`} onClick={() => setTheme(t)}>
              {t}
            </button>
          ))}
        </div>
        <div className="text-xs text-[var(--hb-muted)] mt-1">Primary theme is dark. Preference stored locally.</div>
      </div>

      {/* Daily Brief external workflow wizard (Prompt 10) */}
      <div className="card">
        <div className="font-medium mb-2">Daily Brief (external)</div>
        <div className="text-xs mb-3">
          The app <strong>presents and polishes</strong> a Markdown file generated by an external desktop AI platform (Claude, ChatGPT, Perplexity, or Other).
          This app does <strong>not</strong> generate, author, or rewrite the brief. All content comes from the file your external agent writes to the folder below.
        </div>

        <div className="grid gap-3">
          <label className="flex items-center gap-2 text-xs">
            <input type="checkbox" checked={enabled} onChange={(e) => onToggleEnabled(e.target.checked)} />
            Show Daily Brief on Today
          </label>

          <div>
            <label htmlFor="db-platform" className="text-xs mb-1">External AI platform</label>
            <select
              id="db-platform"
              className="bg-[var(--hb-bg)] border border-[var(--hb-border)] rounded px-2 py-1 text-sm"
              value={platform}
              onChange={(e) => onPlatformChange(e.target.value as any)}
            >
              <option value="claude">Claude (desktop / projects)</option>
              <option value="chatgpt">ChatGPT (Custom GPT / scheduled)</option>
              <option value="perplexity">Perplexity</option>
              <option value="other">Other / manual</option>
            </select>
            <div className="text-[10px] text-[var(--hb-muted)] mt-1">Platform-specific MCP guidance and scheduled prompt are generated for the selection.</div>
          </div>

          <div>
            <label htmlFor="db-output-folder" className="text-xs mb-1">Output folder (local absolute path the external agent will write to)</label>
            <input
              id="db-output-folder"
              className="w-full bg-[var(--hb-bg)] border border-[var(--hb-border)] rounded px-2 py-1 text-sm"
              value={outputFolder}
              onChange={(e) => setOutputFolder(e.target.value)}
              onBlur={onFolderBlur}
              placeholder="~/Documents/HB-Daily-Briefs or /Users/you/DailyBriefs"
              aria-label="Output folder for Daily Brief file"
            />
          </div>

          <div>
            <label htmlFor="db-file-pattern" className="text-xs mb-1">File name pattern</label>
            <input
              id="db-file-pattern"
              className="w-full bg-[var(--hb-bg)] border border-[var(--hb-border)] rounded px-2 py-1 text-sm font-mono"
              value={filePattern}
              onChange={(e) => setFilePattern(e.target.value)}
              onBlur={onPatternBlur}
              aria-label="File name pattern for Daily Brief"
            />
            <div className="text-[10px] text-[var(--hb-muted)]">Example: HB-Daily-Brief-*.md — the external prompt will substitute the date.</div>
          </div>

          <div>
            <label htmlFor="db-stale-minutes" className="text-xs mb-1">Stale threshold (minutes)</label>
            <input
              id="db-stale-minutes"
              type="number"
              className="w-40 bg-[var(--hb-bg)] border border-[var(--hb-border)] rounded px-2 py-1 text-sm"
              value={staleMinutes}
              onChange={(e) => setStaleMinutes(parseInt(e.target.value || '1440', 10))}
              onBlur={onStaleBlur}
              aria-label="Stale threshold minutes for Daily Brief"
            />
            <div className="text-[10px] text-[var(--hb-muted)]">If the file is older than this, Today shows "Brief stale". Typical: 720–1440 (12–24 h).</div>
          </div>

          <label className="flex items-center gap-2 text-xs">
            <input type="checkbox" checked={showOnToday} onChange={(e) => onShowToggle(e.target.checked)} />
            Include in Today dashboard
          </label>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          <button className="badge" disabled={!!busy} onClick={generateInstructions}>
            {busy === 'instructions' ? 'Generating…' : 'Generate setup instructions + scheduled prompt'}
          </button>
          <button className="badge" disabled={!!busy || !outputFolder} onClick={validateFolder}>
            {busy === 'validate' ? 'Validating…' : 'Validate folder'}
          </button>
          <button className="badge" disabled={!!busy} onClick={testDetection}>
            {busy === 'detect' ? 'Detecting…' : 'Test detection'}
          </button>
          <button className="badge" onClick={refreshStatus} disabled={loadingStatus}>
            {loadingStatus ? 'Refreshing…' : 'Refresh status'}
          </button>
        </div>

        {/* Live status / detection preview */}
        <div className="mt-3">
          <div className="text-xs mb-1">Current detection</div>
          <DailyBriefRenderer
            content={previewContent}
            status={currentState || status?.state}
            generatedAt={previewGenerated}
            path={previewPath}
            warnings={previewWarnings}
          />
          <div className="text-[10px] text-[var(--hb-muted)] mt-1">
            Link from Today → Settings for configuration. <Link to="/today" className="underline">Open Today</Link>
          </div>
        </div>

        {/* Validate result */}
        {validateResult && (
          <div className="mt-3 card text-xs">
            <div className="font-medium mb-1">Folder validation</div>
            <div>valid: {String(validateResult.valid)} • exists: {String(validateResult.exists)} • writable: {String(validateResult.writable)}</div>
            <div className="text-[var(--hb-muted)]">{validateResult.message}</div>
            {validateResult.path && <div className="font-mono mt-1">{validateResult.path}</div>}
          </div>
        )}

        {/* Generated instructions + prompt (copyable) */}
        {instrResult && (
          <div className="mt-3 space-y-2">
            <div className="text-xs font-medium">Setup instructions ({instrResult.platform})</div>
            <button className="text-[10px] underline" onClick={() => copy(instrResult.mcp_setup_note + '\n\n' + instrResult.platform_specific + '\n\n' + (instrResult.scheduled_prompt || ''))}>Copy all</button>
            <textarea readOnly className="w-full h-24 text-xs bg-[var(--hb-bg)] border border-[var(--hb-border)] p-2 rounded" value={instrResult.mcp_setup_note || ''} />
            <textarea readOnly className="w-full h-24 text-xs bg-[var(--hb-bg)] border border-[var(--hb-border)] p-2 rounded" value={instrResult.platform_specific || ''} />
            <div className="text-xs font-medium mt-2">Copy-ready scheduled prompt (paste into your external AI scheduler / custom GPT / recurring task)</div>
            <button className="text-[10px] underline" onClick={() => copy(instrResult.scheduled_prompt || '')}>Copy prompt</button>
            <textarea readOnly className="w-full h-64 text-xs bg-[var(--hb-bg)] border border-[var(--hb-border)] p-2 rounded font-mono" value={instrResult.scheduled_prompt || ''} />
            <div className="text-[10px] text-[var(--hb-muted)]">{instrResult.test_steps}</div>
          </div>
        )}

        <div className="advisory mt-3">
          Externally generated Markdown only. This app detects the file and renders a polished executive brief. It does not generate or materially rewrite content.
          Configure the external agent (with MCP where supported) to write the file on schedule and follow the "no raw sensitive" rules in the generated prompt.
        </div>
      </div>

      {/* Prompt D: interactive, safe account connection cards (Graph device-code + Procore OAuth) replace the old Load + raw result block.
          Panel handles its own fetches, polling, and success refresh. No raw JSON for normal users. */}
      <AccountConnectionsPanel variant="settings" />

      {/* Prompt E: interactive auth-aware project connection preview/save (Procore/SharePoint/OneDrive/Outlook-Calendar).
          Replaces the old Load/raw stub. Panel handles preview (viewer), save (operator), list with first_sync_status,
          and auth gating based on current account connections from Prompt D surfaces. */}
      <ProjectConnectionsPanel />

      <div className="card">
        <div className="font-medium mb-2">Source Scope (Prompt 14B)</div>
        <button
          className="text-xs underline mb-2"
          onClick={async () => {
            setSourcesError(null)
            try {
              const s = await getSettingsSources()
              setSourcesResult(s)
            } catch (e: any) {
              setSourcesError(e?.message || String(e))
              setSourcesResult(null)
            }
          }}
        >
          Load Source Scope
        </button>
        <ErrorState
          message={sourcesError}
          onRetry={() => {
            setSourcesError(null)
            ;(async () => {
              try {
                const s = await getSettingsSources()
                setSourcesResult(s)
              } catch (e: any) {
                setSourcesError(e?.message || String(e))
                setSourcesResult(null)
              }
            })()
          }}
        />
        {sourcesResult && (
          <div className="text-xs mt-1">
            Loaded source scope info.
            (status shown above; raw panels removed per FPR-004)
          </div>
        )}
        <div className="text-xs">Business descriptions. Outlook/Calendar: project_matching_only optional, false by default (match after ingestion). OneDrive all-folders: explicit + warning.</div>
      </div>

      <div className="card">
        <div className="font-medium mb-2">Project Matching Keywords (Prompt 14B)</div>
        <button
          className="text-xs underline mb-2"
          onClick={async () => {
            setKeywordsError(null)
            try {
              const k = await getSettingsKeywords()
              setKeywordsResult(k)
            } catch (e: any) {
              setKeywordsError(e?.message || String(e))
              setKeywordsResult(null)
            }
          }}
        >
          Load Keywords Info
        </button>
        <ErrorState
          message={keywordsError}
          onRetry={() => {
            setKeywordsError(null)
            ;(async () => {
              try {
                const k = await getSettingsKeywords()
                setKeywordsResult(k)
              } catch (e: any) {
                setKeywordsError(e?.message || String(e))
                setKeywordsResult(null)
              }
            })()
          }}
        />
        {keywordsResult && (
          <div className="text-xs mt-1">
            Loaded keywords policy/surface info.
            (status shown above; raw panels removed per FPR-004)
          </div>
        )}
        <div className="text-xs">Candidates/active/disabled/excluded. Add/edit/disable/delete/explain. Standard/template folder names rejected by policy. (Prompt 20: full management UI below using safe backend.)</div>

      {/* Prompt 20 keyword management (FPR-017) */}
      <div className="mt-2 border border-[var(--hb-border)] rounded p-2">
        <div className="text-xs font-medium mb-1">Keyword Management (per project)</div>
        <div className="flex gap-2 flex-wrap text-xs items-end">
          <label className="text-[10px]" htmlFor="kw-project">Project key
            <input id="kw-project" className="border px-1 block" placeholder="demo-proj" value={kwProject} onChange={(e) => setKwProject(e.target.value)} aria-label="Project key for keyword management" />
          </label>
          <label className="text-[10px]" htmlFor="kw-term">Term
            <input id="kw-term" className="border px-1 block" placeholder="foundation" value={kwTerm} onChange={(e) => setKwTerm(e.target.value)} aria-label="Keyword term" />
          </label>
          <button className="badge" onClick={async () => {
            if (!kwProject || !kwTerm) return;
            await addProjectKeyword(kwProject, kwTerm, 1);
            const lst = await getProjectKeywords(kwProject);
            setKwList(lst);
          }}>Add</button>
          <button className="badge" onClick={async () => {
            if (!kwProject) return;
            const lst = await getProjectKeywords(kwProject);
            setKwList(lst);
          }}>Load List</button>
          <button className="badge" onClick={async () => {
            if (!kwProject || !kwTerm) return;
            const exp = await explainProjectKeywordMatch(kwProject, kwTerm);
            setKwExplain(exp);
          }}>Explain</button>
        </div>
        {kwList && <div className="text-[10px] mt-1">List: {JSON.stringify(kwList).slice(0, 200)}</div>}
        {kwExplain && <div className="text-[10px] mt-1">Explain: {JSON.stringify(kwExplain).slice(0, 200)}</div>}
        <div className="text-[10px] text-[var(--hb-muted)] mt-1">Edits are safe (no raw content; backend rejects template folders). Refresh list after changes.</div>
      </div>
      </div>

      <div className="card">
        <div className="font-medium mb-2">Daily Brief (Prompt 14B)</div>
        <button
          className="text-xs underline mb-2"
          onClick={async () => {
            setDailyBriefError(null)
            try {
              const d = await getSettingsDailyBrief()
              setDailyBriefResult(d)
            } catch (e: any) {
              setDailyBriefError(e?.message || String(e))
              setDailyBriefResult(null)
            }
          }}
        >
          Load Daily Brief Status
        </button>
        <ErrorState
          message={dailyBriefError}
          onRetry={() => {
            setDailyBriefError(null)
            ;(async () => {
              try {
                const d = await getSettingsDailyBrief()
                setDailyBriefResult(d)
              } catch (e: any) {
                setDailyBriefError(e?.message || String(e))
                setDailyBriefResult(null)
              }
            })()
          }}
        />
        {dailyBriefResult && (
          <div className="text-xs mt-1">
            Daily Brief status available via the section below (no raw panels).
          </div>
        )}
        <div className="text-xs">External Markdown only. 7 states, platform instructions (Claude/ChatGPT/Perplexity/Other), copy scheduled prompt, detect/validate. Presenter-only; no rewrite.</div>
      </div>

      <div className="card">
        <div className="font-medium mb-2">Preferences (Prompt 14B)</div>
        <div className="text-xs mb-1">Theme: dark/light/system (current: {theme})</div>
        <div className="flex gap-2 mb-2">
          <button className="text-xs px-2 py-1 border rounded" onClick={() => setTheme('dark')}>Dark</button>
          <button className="text-xs px-2 py-1 border rounded" onClick={() => setTheme('light')}>Light</button>
          <button className="text-xs px-2 py-1 border rounded" onClick={() => setTheme('system')}>System</button>
        </div>
        <button
          className="text-xs underline mb-2"
          onClick={async () => {
            setPrefsError(null)
            try {
              const pr = await getSettingsPreferences()
              setPrefsResult(pr)
            } catch (e: any) {
              setPrefsError(e?.message || String(e))
              setPrefsResult(null)
            }
          }}
        >
          Load Preferences
        </button>
        <ErrorState
          message={prefsError}
          onRetry={() => {
            setPrefsError(null)
            ;(async () => {
              try {
                const pr = await getSettingsPreferences()
                setPrefsResult(pr)
              } catch (e: any) {
                setPrefsError(e?.message || String(e))
                setPrefsResult(null)
              }
            })()
          }}
        />
        {prefsResult && (
          <div className="text-xs mt-1">
            Loaded preferences.
            (status shown above; raw panels removed per FPR-004)
          </div>
        )}
        <button
          className="text-xs underline"
          onClick={async () => {
            setPrefsPatchMsg(null)
            try {
              await patchSettingsPreferences({ theme, default_landing_page: 'Today' })
              setPrefsPatchMsg('Preferences saved locally.')
            } catch (e: any) {
              setPrefsError(e?.message || String(e))
            }
          }}
        >
          Save simple prefs
        </button>
        {prefsPatchMsg && <div className="text-xs mt-1 text-green-600">{prefsPatchMsg}</div>}
        <div className="text-xs mt-1">Default landing, followed projects, Daily Brief display. Local persistence.</div>
      </div>

      <div className="card">
        <div className="font-medium mb-2">Admin Sync Controls (Prompt 14B, admin only)</div>
        <button
          className="text-xs underline mb-2"
          onClick={async () => {
            setAdminSyncError(null)
            setAdminPatchMsg(null)
            try {
              const ad = await getSettingsAdminSync()
              setAdminSyncResult(ad)
            } catch (e: any) {
              setAdminSyncError(e?.message || String(e))
              setAdminSyncResult(null)
            }
          }}
        >
          Load Admin Sync (admin role)
        </button>
        <ErrorState
          message={adminSyncError}
          onRetry={() => {
            setAdminSyncError(null)
            ;(async () => {
              try {
                const ad = await getSettingsAdminSync()
                setAdminSyncResult(ad)
              } catch (e: any) {
                setAdminSyncError(e?.message || String(e))
                setAdminSyncResult(null)
              }
            })()
          }}
        />
        {adminSyncResult && (
          <div className="text-xs mt-1">
            Loaded admin sync info (admin only).
            (status shown above; raw panels removed per FPR-004)
          </div>
        )}
        <button
          className="text-xs underline"
          onClick={async () => {
            setAdminPatchMsg(null)
            setAdminSyncError(null)
            try {
              await patchSettingsAdmin({ global_rate_limit: 60 })
              setAdminPatchMsg('Admin settings saved.')
            } catch (e: any) {
              setAdminSyncError('Admin only: ' + (e?.message || e))
            }
          }}
        >
          Apply sample admin rate limit (admin)
        </button>
        {adminPatchMsg && <div className="text-xs mt-1 text-green-600">{adminPatchMsg}</div>}
        <div className="text-xs">Pending approvals, cadence/priority, rate-limit/backoff. CM User/operator cannot approve first sync.</div>
      </div>

      <div className="card">
        <div className="font-medium mb-2">Local Storage / Retention (Prompt 14B)</div>
        <div className="text-xs">Usage, evidence/Daily Brief retention, cleanup. Local-first under Application Support. Real persistence for preferences (Prompt 20).</div>
      </div>

      <div className="advisory">All settings respect local-first, read-only, advisory-only guardrails. No secrets or tokens are stored or displayed here. Daily Brief configuration is stored locally under Application Support. Chat is disabled and future-only.</div>
    </div>
  )
}
