import { useTheme } from '../app/providers'

// Settings per 13: theme, Daily Brief folder pattern (present-only), connection status, keyword registry entry points, etc.
// Keep lightweight for UI-08.

export function SettingsPage() {
  const { theme, setTheme } = useTheme()
  return (
    <div className="max-w-xl space-y-4 text-sm">
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

      <div className="card">
        <div className="font-medium mb-2">Daily Brief (external)</div>
        <div className="text-xs">App presents/polishes an externally generated Markdown file. It does not generate or rewrite the brief.</div>
        <div className="mt-2 text-xs">Output folder / file pattern and show/hide on Today are configured via the external agent workflow (see package docs).</div>
      </div>

      <div className="card">
        <div className="font-medium mb-2">Connections &amp; Onboarding</div>
        <div className="text-xs">Graph / Procore / SharePoint / OneDrive status and first-run flows live behind the FastAPI surfaces (future UI-03/04). Current surfaces are read-only status in Admin.</div>
      </div>

      <div className="card">
        <div className="font-medium mb-2">Project Keywords</div>
        <div className="text-xs">Training, exclusions (standard folder names rejected), strength, provenance. CRUD behind /api (Prompt 05). Edit/disable/delete supported for operators/admins.</div>
      </div>

      <div className="advisory">All settings respect local-first, read-only, advisory-only guardrails. No secrets or tokens are stored or displayed here.</div>
    </div>
  )
}
