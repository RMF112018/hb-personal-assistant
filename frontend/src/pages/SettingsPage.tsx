import { useEffect, useState } from 'react'
import { useTheme } from '../app/providers'
import { DailyBriefRenderer } from '../components/daily-brief/DailyBriefRenderer'
/* eslint-disable @typescript-eslint/no-explicit-any */
import {
  getDailyBriefStatus,
  configureDailyBrief,
  generateDailyBriefSetupInstructions,
  validateDailyBriefOutputFolder,
  detectDailyBriefLatest,
} from '../lib/api'

// Settings (Prompt 10 / UI-12 partial for Daily Brief): external-agent Markdown setup wizard.
// Enable/disable, platform selector (Claude/ChatGPT/Perplexity/Other), output folder + pattern,
// stale threshold, show/hide on Today. Buttons for generate instructions (includes copy-ready
// scheduled prompt + MCP guidance), validate folder, test detection.
// Business language; strong "presents/polishes only" contract; no in-app generation.

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
    } catch (e: any) {
      alert(`Configure failed: ${e?.message || e}`)
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
    } catch (e: any) {
      alert(`Generate instructions failed: ${e?.message || e}`)
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
    } catch (e: any) {
      alert(`Validate failed: ${e?.message || e}`)
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
    } catch (e: any) {
      alert(`Detect failed: ${e?.message || e}`)
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

  const currentState = detectResult?.state || status?.state || status?.config?.enabled === false ? 'not_configured' : undefined
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
            <div className="text-xs mb-1">External AI platform</div>
            <select
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
            <div className="text-xs mb-1">Output folder (local absolute path the external agent will write to)</div>
            <input
              className="w-full bg-[var(--hb-bg)] border border-[var(--hb-border)] rounded px-2 py-1 text-sm"
              value={outputFolder}
              onChange={(e) => setOutputFolder(e.target.value)}
              onBlur={onFolderBlur}
              placeholder="~/Documents/HB-Daily-Briefs or /Users/you/DailyBriefs"
            />
          </div>

          <div>
            <div className="text-xs mb-1">File name pattern</div>
            <input
              className="w-full bg-[var(--hb-bg)] border border-[var(--hb-border)] rounded px-2 py-1 text-sm font-mono"
              value={filePattern}
              onChange={(e) => setFilePattern(e.target.value)}
              onBlur={onPatternBlur}
            />
            <div className="text-[10px] text-[var(--hb-muted)]">Example: HB-Daily-Brief-*.md — the external prompt will substitute the date.</div>
          </div>

          <div>
            <div className="text-xs mb-1">Stale threshold (minutes)</div>
            <input
              type="number"
              className="w-40 bg-[var(--hb-bg)] border border-[var(--hb-border)] rounded px-2 py-1 text-sm"
              value={staleMinutes}
              onChange={(e) => setStaleMinutes(parseInt(e.target.value || '1440', 10))}
              onBlur={onStaleBlur}
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
            Link from Today → Settings for configuration. <a className="underline" href="#/today">Open Today</a>
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

      <div className="card">
        <div className="font-medium mb-2">Connections &amp; Onboarding</div>
        <div className="text-xs">Graph / Procore / SharePoint / OneDrive status and first-run flows live behind the FastAPI surfaces (future UI-03/04). Current surfaces are read-only status in Admin.</div>
      </div>

      <div className="card">
        <div className="font-medium mb-2">Project Keywords</div>
        <div className="text-xs">Training, exclusions (standard folder names rejected), strength, provenance. CRUD behind /api (Prompt 05). Edit/disable/delete supported for operators/admins.</div>
      </div>

      <div className="advisory">All settings respect local-first, read-only, advisory-only guardrails. No secrets or tokens are stored or displayed here. Daily Brief configuration is stored locally under Application Support.</div>
    </div>
  )
}
