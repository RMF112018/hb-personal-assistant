# 189 - Frontend Shell Viewport and Production Chrome

Date: 2026-06-07

Package: Frontend UI/UX Shell Layout Implementation Package

## Decision

The analytics frontend shell uses a bounded viewport layout. The root document, React root, app shell, sidebar, and main frame are constrained so page content scrolls inside the main content region instead of pushing the browser document or sidebar footer.

The sidebar footer is a dedicated shell component that remains outside page scroll. It contains the non-admin Data Quality indicator and support navigation. Disabled future Chat affordances are not rendered in production chrome.

## Rationale

The shell is an operations dashboard, so primary navigation and status context must stay stable while dense Today, Projects, and My Items pages scroll. A single main scroll container also avoids footer displacement caused by flex children that lack `min-h-0`.

Development role simulation remains a request-header concern in the frontend API client, but the normal user interface no longer exposes role-switching copy or controls. Admin navigation visibility is derived from the local UI role and backend guards remain authoritative.

## Constraints

- No Chat route or Chat surface is introduced.
- No backend auth behavior changes.
- No sync, source-system reads, SQLite writes, auth-cache access, or Obsidian access are part of this shell change.
- Page-level validation must still confirm navigation active states, mobile navigation access, and no document-level horizontal overflow.
