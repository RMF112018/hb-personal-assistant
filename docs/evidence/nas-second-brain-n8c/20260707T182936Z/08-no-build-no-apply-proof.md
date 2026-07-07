# 08 — No-build / no-apply proof

The MCP handler only calls `WorkflowRouter.route()` / `.catalog()`, which the N8C-15 layer already proves
(AST test) never call a build/apply writer, source scan/reindex, source-card generator, enrichment/qwen
worker, or LLM. N8C-16 adds no new call path: the AST guard `test_handler_calls_no_writer_or_source_read`
re-proves this scoped to the workflow handler + views. When a required artifact is absent the envelope
carries `status=missing_required_artifact` + deferred markers — the router never builds it.
