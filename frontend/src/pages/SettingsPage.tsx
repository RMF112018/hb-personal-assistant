import { useState } from 'react'

import { useTheme } from '../app/providers'
import { AdminFirstSyncApprovalPanel } from '../components/settings/AdminFirstSyncApprovalPanel'
import { AccountConnectionsPanel } from '../components/settings/AccountConnectionsPanel'
import { SourceConnectionsPanel } from '../components/settings/SourceConnectionsPanel'
import { DailyBriefSettingsPanel } from '../components/settings/DailyBriefSettingsPanel'
import { DataHealthPanel } from '../components/settings/DataHealthPanel'
import { KeywordManagementPanel } from '../components/settings/KeywordManagementPanel'
import { ProjectConnectionsPanel } from '../components/settings/ProjectConnectionsPanel'
import { DashboardGrid } from '../components/layout/DashboardGrid'
import { PrimaryPageLayout } from '../components/layout/PrimaryPageLayout'
import { SectionCard } from '../components/common/SectionCard'
import { ErrorState } from '../components/common/ErrorState'
import { patchSettingsPreferences } from '../lib/api'

export function SettingsPage() {
  const { theme, setTheme } = useTheme()
  const [savingPrefs, setSavingPrefs] = useState(false)
  const [prefsMessage, setPrefsMessage] = useState<string | null>(null)
  const [prefsError, setPrefsError] = useState<unknown>(null)

  async function savePreferences() {
    setSavingPrefs(true)
    setPrefsMessage(null)
    setPrefsError(null)
    try {
      await patchSettingsPreferences({ theme, default_landing_page: 'Today' })
      setPrefsMessage('Preferences saved.')
    } catch (error) {
      setPrefsError(error)
    } finally {
      setSavingPrefs(false)
    }
  }

  return (
    <PrimaryPageLayout>
      <DashboardGrid columns="sections" gap="lg">
        <AccountConnectionsPanel variant="settings" />
        <SourceConnectionsPanel />
        <ProjectConnectionsPanel />
        <DailyBriefSettingsPanel />

        <SectionCard title="Preferences" description="Choose how the app appears on this device.">
          <div className="flex flex-wrap gap-2">
            {(['dark', 'light', 'system'] as const).map((option) => (
              <button
                key={option}
                className={`badge ${theme === option ? 'ring-1 ring-[var(--hb-accent)]' : ''}`}
                onClick={() => setTheme(option)}
              >
                {option}
              </button>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <button className="badge" onClick={savePreferences} disabled={savingPrefs}>
              {savingPrefs ? 'Saving...' : 'Save preferences'}
            </button>
          </div>
          {prefsMessage && <div className="mt-2 text-xs text-green-600">{prefsMessage}</div>}
          <ErrorState userMessage="Preferences could not be saved." error={prefsError} />
        </SectionCard>

        <KeywordManagementPanel />
        <DataHealthPanel />
        <AdminFirstSyncApprovalPanel />
      </DashboardGrid>
    </PrimaryPageLayout>
  )
}
