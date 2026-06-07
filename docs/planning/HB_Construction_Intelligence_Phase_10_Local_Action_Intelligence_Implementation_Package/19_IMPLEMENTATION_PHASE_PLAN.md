# 19 Implementation Phase Plan

## Recommended commit sequence

1. Rebaseline and contracts/seeds.
2. Schema V41 additive migration.
3. Local model runtime/status.
4. AI job queue.
5. Candidate output contracts and fixture runner.
6. Task/commitment extraction.
7. Follow-up monitor.
8. Relationship candidate engine.
9. Daily Brief action candidates.
10. Obsidian vault manager MVP.
11. MCP context packet builder.
12. Backend API endpoints for dashboard/review queue.
13. Frontend My Dashboard / Review Queue.
14. Data Health/Admin Phase 10 status.
15. No-raw/no-writeback proofs and closeout.

## Integration with source refresh

After source refresh rebuild, enqueue bounded Phase 10 jobs in dry-run/local-only mode unless config permits apply to local candidate tables.
