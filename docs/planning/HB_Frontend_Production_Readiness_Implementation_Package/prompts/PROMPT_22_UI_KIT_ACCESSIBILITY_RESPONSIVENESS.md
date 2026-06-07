# Prompt 22 — UI kit, accessibility, responsiveness consolidation

Repository: `RMF112018/hb-personal-assistant`  
Working path: `/Users/bobbyfetting/hb-personal-assistant`  
Prompt dependency: Prompt 21 should be closed or explicitly waived with evidence.

## Objective

Create a coherent lightweight frontend component layer and accessibility/responsiveness baseline.

## Repo-Truth First Step

Before changing files, run the preflight commands in `02_REPO_TRUTH_PREFLIGHT.md` or update the existing preflight evidence if it has already been run in this implementation sequence. Repository truth is authoritative over this package.

## Gaps Addressed

### FPR-011 — alert() error handling remains in Settings

- Severity: P2
- Affected area: Frontend error handling
- Recommended fix: Use shared inline ErrorState/Toast-like component with retry actions.
- Validation: grep no alert(; manual failure smoke

### FPR-013 — Responsive/accessibility baseline is incomplete

- Severity: P2
- Affected area: Styling / UI kit
- Recommended fix: Add responsive sidebar collapse, focus styles for inputs/selects, skip link, semantic regions, form labels, and accessible loading/error states.
- Validation: axe/manual a11y smoke; keyboard navigation smoke; responsive viewport smoke


## Scope

- Consolidate repeated card, section, badge, loading, empty, and error patterns into reusable components.
- Replace remaining `alert()` handling with inline errors or a lightweight toast/status pattern.
- Add focus-visible styles for anchors, buttons, inputs, selects, textareas, and role selector controls.
- Add skip link and semantic landmarks where practical.
- Improve sidebar behavior for narrow widths without overbuilding.
- Keep Tailwind/Radix/shadcn-style primitives coherent; do not re-platform.

## Non-Scope

- Full custom design system.
- Major visual redesign disconnected from current pages.
- New charts or complex interaction patterns unless already scoped by prior prompts.

## Files Likely Touched

- `frontend/src/components/ui/*`
- `frontend/src/components/dashboard/*`
- `frontend/src/components/settings/*`
- `frontend/src/components/projects/*`
- `frontend/src/layouts/*`
- `frontend/src/index.css`
- `frontend/src/App.tsx`

## Implementation Guidance

- Prefer typed adapters and explicit view-model normalization over permissive `any` fallbacks.
- Preserve the current safety boundaries: no source-system writeback, no active chat, no raw/secrets serialization, no setup-triggered live sync.
- Keep the UI construction-management-first and avoid backend-console labels.
- Update tests and evidence in the same prompt; do not defer validation to a later session unless blocked by environment.
- When a gap is already fixed in current repo truth, document the evidence and do not rework the code unnecessarily.

## Acceptance Criteria

- No `alert()` calls remain in frontend source.
- Core pages use consistent cards/sections/badges/loading/empty/error states.
- Keyboard users can navigate top-level nav and forms.
- Narrow viewport is usable.
- Focus states are visible and consistent.

## Validation Commands

- `cd frontend && npm run lint && npm run typecheck && npm run build`
- `grep -R "alert(" -n frontend/src || true`
- `Manual keyboard smoke: tab through shell, role selector, Today, Settings forms`
- `Responsive smoke at common narrow desktop/tablet widths`

## Evidence Required

Create or update:

```text
docs/evidence/frontend-production-readiness-implementation/prompt-22-ui-kit-accessibility-responsiveness-closeout.md
```

Include branch, HEAD, files changed, gaps closed/deferred, validation command output summary, browser smoke notes, and guardrail confirmation.

## Risk Notes

- Do not introduce heavy dependencies unless justified.
- Avoid spending time on visual novelty before route stability.
