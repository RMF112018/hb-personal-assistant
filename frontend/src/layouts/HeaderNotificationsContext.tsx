import { createContext, useContext, useState } from 'react'
import type { ReactNode } from 'react'

export type HeaderNotificationsContextValue = {
  notifications: ReactNode | null
  setNotifications: (nodes: ReactNode | null) => void
}

const HeaderNotificationsContext = createContext<HeaderNotificationsContextValue | undefined>(undefined)

/**
 * Provider that holds the current page-provided notifications/warnings to be shown in the AppShell chrome header.
 * Primary pages (via their StatusRows) publish their data quality chips here so they appear at chrome level.
 */
export function HeaderNotificationsProvider({ children }: { children: ReactNode }) {
  const [notifications, setNotifications] = useState<ReactNode | null>(null)
  return (
    <HeaderNotificationsContext.Provider value={{ notifications, setNotifications }}>
      {children}
    </HeaderNotificationsContext.Provider>
  )
}

/**
 * Hook for page-level components (e.g. *StatusRow) to publish compact quality chips into the shell header.
 * In test renders that don't wrap AppShell, returns a safe no-op so components don't explode.
 */
// eslint-disable-next-line react-refresh/only-export-components -- hook + type live alongside the provider component; this is intentional and small.
export function useHeaderNotifications() {
  const ctx = useContext(HeaderNotificationsContext)
  if (!ctx) {
    // Graceful fallback for isolated page tests and any content outside the shell chrome.
    return { notifications: null, setNotifications: () => {} }
  }
  return ctx
}
