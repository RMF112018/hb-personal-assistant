# PM Readiness Findings

**STAMP:** 20260701T081419Z  
**Proof type:** repo truth + live browser walkthrough

## F1 — Driver detail title demotes activity name

- **Surface:** `ProjectScheduleDriverDetailPage.tsx`
- **Impact:** PM sees generic “Driver Detail” instead of the movement activity
- **Severity:** P1
- **Proposed fix:** H3 = activity name; subtitle “Driver detail” + named comparison context line
- **Out of scope:** no

## F2 — Named Workbench read-only posture buried

- **Surface:** `ProjectScheduleWorkbenchPage.tsx`
- **Impact:** PM may think dispositions sync on named baseline preview
- **Severity:** P1
- **Proposed fix:** Prominent read-only banner + named comparison context
- **Out of scope:** no

## F3 — Controls lack comparison-anchor context

- **Surface:** `ScheduleControlsPanel.tsx`
- **Impact:** Active named baseline not obvious when controls are available
- **Severity:** P1
- **Proposed fix:** “Comparing against {slot} · {date · name}” context line
- **Out of scope:** no

## F4 — Baseline anchor missing/invalid copy weak

- **Surface:** `ScheduleBaselineSelector.tsx`, `ScheduleControlsPanel.tsx`
- **Impact:** PM unsure what to do when anchor unset or invalid
- **Severity:** P1
- **Proposed fix:** Actionable missing copy; humanized unavailable reasons
- **Out of scope:** no

## F5 — Driver error text exposes internal params

- **Surface:** `ProjectScheduleDriverDetailPage.tsx`
- **Impact:** `comparison_basis` / `basis` visible in error UI
- **Severity:** P1
- **Proposed fix:** PM-facing conflict/invalid messages without enum names
- **Out of scope:** no

## F6 — Logic changes show raw activity IDs

- **Surface:** `ProjectScheduleDriverDetailPage.tsx`
- **Impact:** Raw IDs in primary card when logic changes exist
- **Severity:** P1
- **Proposed fix:** Humanized relationship summary; IDs only in technical details
- **Out of scope:** no

## F7 — Driver detail missing advisory footer

- **Surface:** `ProjectScheduleDriverDetailPage.tsx`
- **Impact:** Non-causation posture less visible on driver path
- **Severity:** P2 → **P1** (controls already have footer; parity needed)
- **Proposed fix:** Match controls advisory footer copy
- **Out of scope:** no

## F8 — Hub section order (Controls before Anchors)

- **Surface:** `ProjectSchedulePage.tsx`
- **Impact:** Theoretical workflow order concern
- **Severity:** P2
- **Proposed fix:** None — walkthrough did not confirm PM confusion at P0/P1
- **Out of scope:** yes (per amendment)

## F9 — Focus driver link shows raw ID

- **Surface:** `ProjectSchedulePage.tsx` (rare deep link)
- **Impact:** Raw `?driver=` ID in link label
- **Severity:** P2
- **Proposed fix:** “Open focused driver detail” without ID in label
- **Out of scope:** no (minimal one-line change)
