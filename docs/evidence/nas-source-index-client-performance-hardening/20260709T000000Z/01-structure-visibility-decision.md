# Structure visibility decision

**Decision: Option A — enable bounded structure tools default-ON.**

## Rationale
- All 7 structure tools are read-only, RO-snapshot, bounded, root-relative, no live recursive scan.
- Default-OFF left connected clients on file-search-only for NAS map prompts (confirmed product gap).
- No residual safety reason beyond the original "don't change live surface" freeze after V115 land; that freeze is now intentionally lifted for map capability.
- Kill-switch remains: `HB_MCP_ASSISTANT_SOURCE_STRUCTURE=0`.

## Default-visible set after change
Structure (default ON): root_map, folder_map, folder_summary, search_route, scope_explain, project_map, quality  
Connector additions (default ON): assistant_source_index_health, assistant_source_query_plan  
Plus existing connector file tools.

## Counts (target)
- Installed/exposed default: **87** assistant tools / 14 groups (was 85 installed / 78 default-exposed)
- Kill-switch OFF for structure: 80 exposed (87 - 7)
