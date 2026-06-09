# Model-unavailable proof — follow-up watch report is deterministic

The follow-up watch report uses **no local model** (classification is pure/deterministic; `now_utc` is the only time seam). A missing/unreachable Ollama daemon never affects it — it always degrades to the same deterministic output.

- `guardrails.deterministic_no_model`: **True**
- repeated build yields identical counts: **True**
- counts: `{"needs_bobby_action": 1, "waiting_on_others": 1, "stale_no_response": 1, "monitor_only": 1, "closed_resolved": 1, "needs_review": 1, "total": 6}`

Optional local-model enrichment (V45) remains a separate, fail-closed advisory route (`follow-up-watch enrich`); it never gates this report.
