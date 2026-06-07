# Scope and Non-Scope

## In scope

- Dev UI Graph and Procore connection surfaces.
- Backend environment/source status routes safe for browser use.
- Graph metadata-only status and safe auth start/status/refresh routes where supported.
- Procore metadata-only status and safe OAuth/status/refresh routes where supported.
- Source refresh dry-run/local/live route separation.
- Scheduler/source-refresh/daily-brief status surfacing.
- Typed frontend API client methods.
- Graph and Procore connection cards.
- Data Quality indicator in the sidebar footer.
- User-facing copy remediation.
- Backend/frontend tests and manual Dev browser validation.

## Non-scope

- Graph writeback.
- Procore writeback.
- External system writes or mutations.
- Raw email/calendar/Procore payload storage or UI exposure.
- Vector/retrieval/MCP/second-brain changes.
- Obsidian writes.
- Desktop packaging or macOS Automator shortcut work.
- Production scheduler install/uninstall changes.

## Guardrail interpretation

Status routes may inspect local config, token-cache metadata, scope metadata, expiry metadata, mapping metadata, local sync receipts, and live-read gate flags.

Status routes must not call Graph content APIs, Procore content APIs, indexing, sync, source-refresh, DB writes, or token mutations.

Auth refresh routes may update token cache only if the action is explicitly initiated. They must not trigger source reads or sync.

Live refresh must fail closed unless backend config and explicit confirmation both allow it.
