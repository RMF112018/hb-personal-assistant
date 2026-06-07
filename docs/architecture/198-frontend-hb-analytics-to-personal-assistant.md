# 198. Frontend HB Analytics to Personal Assistant Rebrand

Date: 2026-06-07

Package: Frontend UI/UX Shell Layout Implementation Package (P09 follow-up)

## Decision

Replace the remaining user-facing display strings that branded the shipped shell as "HB Analytics" (and the variant "HB • Analytics" in the document title) with "Personal Assistant".

Files edited (only):
- `frontend/index.html`: `<title>HB • Analytics</title>` → `<title>Personal Assistant</title>`
- `frontend/src/layouts/AppShell.tsx`:
  - `const headerTitle = 'HB Analytics'` → `'Personal Assistant'`
  - `return 'HB Analytics'` (getPageTitle fallback) → `'Personal Assistant'`

Scope strictly limited to these three user-facing rendered strings (browser tab title, persistent header chrome label, and the catch-all page title). No other occurrences were modified:
- `frontend/src/index.css` comment left as-is (implementation note, not user-facing).
- `frontend/README.md` heading left as-is (package history / contributor doc).
- All lower-case "analytics" references in source paths, comments, vite proxy notes, backend module names, tests, planning docs, evidence, architecture notes, and runbooks were left untouched (they refer to the internal "FastAPI analytics shell" / "analytics-ui" optional or historical package names, not the end-user brand).

This is a pure display-copy remediation with no behavior, data, auth, routing, or test changes. The three prior P0/P1 gaps addressed by the parent package remain closed; this is a follow-up hygiene item for the user-facing name.

Post-edit obligations executed (per originating query):
- Architecture documentation updated with this ADR (198).
- The package verification suite executed exactly (copycheck first, then the rest of the frontend chain + the four pytest commands from repo root).
- Traditional commit prepared using manifest title "frontend-ui-ux-shell-layout-implementation-package" and version "2026-06-07 / 0.0.0"; only the three deltas staged and committed.
- Agent final output is solely the commit summary line + full description.

## Rationale

The originating request explicitly authorized replacing "any user facing reference to `HB Analytics` with `Personal Assistant` through the entirety of the relevant repo files." The prior P07–P09 work had already removed most telemetry and dev-only jargon; these two remaining branded strings were the last user-visible holdovers in the production chrome (header) and document title.

Limiting the edit to the runtime display surfaces (index.html title and the two string literals in AppShell that feed the visible header and PageHeader) satisfies the request while respecting the non-scope guidance from the package (do not broadly rename internal "analytics" concepts that are implementation-layer or historical).

The change is safe, minimal, and observable immediately in the shell title bar and browser tab.

## Guardrails

- Only user-facing strings touched; zero impact on functionality, copy regression harness, tests, or contracts.
- No new dependencies or build changes.
- Full listed verification suite re-run after the edit (even though trivial) to prove the tree remains green.
- Commit hygiene: exactly three paths added (`frontend/index.html`, `frontend/src/layouts/AppShell.tsx`, `docs/architecture/198-frontend-hb-analytics-to-personal-assistant.md`); all other dirty files from prior work ignored.
- Safety: this run performed only source string edits + docs + evidence-of-run (verification output captured); no external systems, tokens, accounts, Obsidian writes, or data mutations of any kind.
- Read discipline observed: never Read the phase README, the P09 plan attachment, or any file under `docs/planning/frontend-ui-ux-shell-layout-implementation-package/` (including its prompts/); Grep/Shell/Glob + the two authorized runtime source Reads + the new ADR Write only.
- The ADR itself follows the established 197 style and package conventions for traceability.

The parent package's P0/P1 closure and the copy regression harness (npm run copycheck) continue to protect the surface. Future work touching the shell header or document title must preserve "Personal Assistant" (or update this record if a further rebrand occurs).
