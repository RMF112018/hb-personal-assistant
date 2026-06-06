// Declarative CM-first navigation model (Prompt 08 + 11 + navigation_model.json alignment)
// Primary top-level, support nav, and explicit disabled (Chat + domain tabs are contextual only).

export type NavItem = {
  label: string
  route: string
  disabled?: boolean
  title?: string
}

export const PRIMARY_NAV: NavItem[] = [
  { label: 'Today', route: '/today' },
  { label: 'Projects', route: '/projects' },
  { label: 'My Items', route: '/my-items' },
]

export const SUPPORT_NAV: NavItem[] = [
  { label: 'Admin / Data Confidence', route: '/admin' },
  { label: 'Settings', route: '/settings' },
]

export const DISABLED_NAV: NavItem[] = [
  { label: 'Chat', route: '/chat', disabled: true, title: 'Future feature only. No active chat page, widget, or route.' },
]

// Domain areas that MUST NOT be top-level nav (they are tabs/sections inside Today, Projects, My Items)
export const CONTEXTUAL_ONLY: string[] = [
  'Portfolio',
  'Meetings',
  'Action Items',
  'Cost / Change',
  'Documents',
  'Correspondence',
  'Vendors',
  'Billing / Cash',
  'Closeout',
  'Field Operations',
]

export function isActive(currentPath: string, itemRoute: string): boolean {
  if (itemRoute === '/projects') {
    return currentPath === '/projects' || currentPath.startsWith('/projects/')
  }
  return currentPath === itemRoute || currentPath.startsWith(itemRoute + '/')
}

export const NAV_MODEL = {
  primary: PRIMARY_NAV,
  support: SUPPORT_NAV,
  disabled: DISABLED_NAV,
  contextualOnly: CONTEXTUAL_ONLY,
}
