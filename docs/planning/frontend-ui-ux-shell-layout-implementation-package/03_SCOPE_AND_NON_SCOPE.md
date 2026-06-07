# Scope and Non-Scope

## In scope

- Frontend shell layout and root height behavior.
- Sidebar primary/support navigation and pinned footer/status region.
- Data Quality footer indicator placement and non-admin/admin visibility logic.
- Today, Projects, and My Items layout refactors.
- Shared dashboard/card/page/state components.
- Settings page user-facing rewrite.
- Admin/Data Confidence naming and business-readable Data Health copy.
- Shared loading/error/empty/disconnected-state copy.
- Frontend API client helpers where needed to consume existing normalized backend routes.
- Copy regression harness and documentation.
- Manual browser smoke testing at desktop/tablet/mobile widths.

## Non-scope

- Implementing new Microsoft Graph authentication.
- Implementing new Procore authentication.
- Starting live external reads.
- Triggering sync jobs.
- Modifying daily brief generation logic or external-agent contracts.
- Modifying retrieval, MCP, embeddings, memory, or source-system writeback.
- Writing to operator SQLite databases.
- Modifying auth caches.
- Writing to Obsidian vault.
- Creating or enabling Chat.

## Safe backend touch boundary

Backend code should be touched only if tests reveal a mismatch in already-existing frontend route contracts. The preferred implementation is frontend-only consumption of existing normalized routes, not backend behavior changes.
