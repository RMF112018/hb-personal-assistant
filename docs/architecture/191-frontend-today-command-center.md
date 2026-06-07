# 191 - Frontend Today Command Center

Date: 2026-06-07

Package: Frontend UI/UX Shell Layout Implementation Package

## Decision

The Today page is structured as a command-center dashboard using the shared frontend layout, grid, card, state, and safe-copy primitives. High-priority content appears first in DOM and visual order, followed by Daily Brief, meetings, action items, recent changes, correspondence, documents, and cost/change/time signals.

Normal Today UI avoids backend, route, pipeline, or raw object fallback language. Technical details are allowed only in collapsed disclosures.

## Rationale

Today is the primary workday surface. It needs to be scan-friendly, responsive, and business-readable before broader page-level refactors continue. Centralizing Today card rendering on shared primitives reduces layout drift and keeps empty/error handling consistent.

## Constraints

- No Daily Brief generation behavior changes.
- No backend route, sync, external-agent, MCP, SQLite, auth-cache, or Obsidian behavior changes.
- No JavaScript masonry dependency is introduced.
- Dashboard cards preserve semantic headings and DOM reading order.
