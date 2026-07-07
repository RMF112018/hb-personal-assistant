# 02 — Current-state audit (before N8C-15)

Before N8C-15, the N8C substrate had read surfaces for each subsystem (source connector, research
packets, answer drafts, intelligence projections, review queue, decision memory, memory, context
packs, claims) but **no unified contract** describing how an assistant workflow should request and
consume them. There was no deterministic router mapping a bounded "workflow request" to the correct
existing artifact surface, and no normalized result envelope.

N8C-15 closes exactly that gap — the contract/routing layer — without advancing into live MCP
consumption (N8C-16), full workflow implementations (N8C-17), or action staging (N8C-18).

## Repository interfaces bound (verified read-only)
Every repository is `Repo(db_path)`; every read method threads an optional `conn=`. Single getters
used by the router: `AnswerDraftRepository.get_answer_draft`, `ResearchPacketRepository.get_research_packet`,
`IntelligenceProjectionRepository.get_projection`, `ContextPackRepository.get_pack`,
`MemoryRepository.get_node`, `DecisionMemoryRepository.get_decision|get_preference|get_open_loop` +
`list_open_loops`, `ReviewRepository.effective_state_for_target`. No writer/build/apply method is
referenced (proven by AST scan in `tests/test_workflow_router.py`).
