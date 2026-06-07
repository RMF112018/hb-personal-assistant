# P08 — Visual Hierarchy, Responsiveness, and Accessibility Hardening

## Objective

Harden the shell and primary pages for production-grade visual hierarchy, density, dark-mode contrast, responsive behavior, and accessibility.

## Scope

- Shell spacing, typography, card hierarchy, dark-mode contrast.
- Today, Projects, My Items card density and grid behavior.
- Focus/hover states.
- Heading hierarchy and landmarks.
- Skip link preservation.
- Tablet/mobile/narrow viewport behavior.

## Required implementation

1. Standardize page header spacing and card gaps.
2. Ensure cards have consistent borders/backgrounds/shadows in dark mode.
3. Ensure interactive elements have visible focus states.
4. Confirm headings are semantic and sequential.
5. Confirm `main`, `nav`, headers, and footer/status regions have coherent labels.
6. Confirm no horizontal overflow at common viewport widths.
7. Confirm dashboard grids collapse gracefully to one column.

## Non-scope

- Do not redesign brand identity.
- Do not add a component library dependency unless repo truth already supports it.

## Acceptance criteria

- Today/Projects/My Items feel consistent and scannable.
- Narrow/mobile layout is usable.
- Keyboard navigation order matches visual/DOM order.
- Screen-reader landmarks and headings are coherent.
- No card overlap/clipping or footer displacement.

## Validation

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
npm run test
```

Manual smoke matrix:

- Desktop: 1440x900 or similar.
- Tablet: approximately 768px wide.
- Narrow/mobile: approximately 390px wide.
- Keyboard-only navigation.
- Browser zoom at 125% if feasible.
