# 193. Frontend My Items Work Queue

Date: 2026-06-07

Package: Frontend UI/UX Shell Layout Implementation Package

## Decision

My Items uses the shared primary layout, dashboard grid, dashboard card, and common state primitives to present a personal work queue. Action Items appear first, followed by meetings, correspondence, files, and followed projects.

The page continues to consume only the aggregate `/api/my-items` envelope. Section data is derived from explicit section arrays when present, with the existing `attention_items` fallback filters preserved.

## Rationale

My Items should help a user scan work assigned to them or waiting for review. Normal page copy should not explain mailbox, calendar, source mechanics, diagnostics, admin approval internals, or implementation constraints.

## Guardrails

- Do not add My Items section subroutes or backend requests.
- Use `safeDisplayText` for object-like queue items so raw JSON is not normal page copy.
- Keep setup and connection actions pointed to Settings.
- Keep project management and followed-project navigation pointed to Projects.
