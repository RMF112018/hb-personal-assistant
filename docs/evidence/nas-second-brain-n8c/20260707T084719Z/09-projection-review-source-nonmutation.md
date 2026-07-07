# 09 — Projection + Review + Source Non-Mutation

## Design
- Builder reads N8C-10 projections via the projection repository with **read-only queries only**
  (`get_projection`, `list_projection_items(..., conn=)`), consuming frozen effective_state / inclusion_state
  / anchors / digests. It never issues UPDATE/INSERT/DELETE against projection, review overlay, or
  source-advisory (claims / enrichment / context-pack / memory / decision) tables.
- `ResearchPacketRepository.upsert_packet(...)` writes **only** the 5 `assistant_research_packet*` tables.
- Every MCP read path opens a read-only snapshot (`_ro_uri(...)` + `PRAGMA query_only=ON`) and threads
  `conn=`.

## Proof (test_research_packet_repository.py + test_research_packet_builder.py)
- `upsert_packet` writes only packet tables; projection + review + source tables unmutated (row counts /
  digests unchanged across preview → dry-run → apply).
- preview + dry-run are read-only; projection/review/source snapshot unchanged.

Packets are materialized read products — never written back into projection/review/source tables.
