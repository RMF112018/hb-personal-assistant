// Declarative CM-first navigation model (Prompt 08 + 11 + navigation_model.json alignment)
// Primary top-level, support nav, and explicit disabled (Chat + domain tabs are contextual only).

export type NavItem = {
  label: string
  route: string
}

export const PRIMARY_NAV: NavItem[] = [
  { label: 'Today', route: '/today' },
  { label: 'Projects', route: '/projects' },
  { label: 'My Items', route: '/my-items' },
]

export const SUPPORT_NAV: NavItem[] = [
  { label: 'Data Health', route: '/admin' },
  { label: 'Settings', route: '/settings' },
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
  contextualOnly: CONTEXTUAL_ONLY,
}
