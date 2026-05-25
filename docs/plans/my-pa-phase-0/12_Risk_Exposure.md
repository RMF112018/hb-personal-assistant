# Risk Exposure

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Delegated proof fails | High | Stop and document exact scope/consent issue. |
| App-only token used for runtime | High | Token classifier fail-closed and tests. |
| Write-capable file scopes | High | No write methods; approval gate. |
| Token cache exposure | High | Application Support, 700/600, clear-cache, scan. |
| Email/file content leakage | High | Redaction and no full content logs. |
| Obsidian overwrite | High | Marker writer and byte preservation tests. |
| Large file performance | Medium | Caps/timeouts/manual approval. |
| Hallucinated action | High | Schema/source/confidence validation. |
| launchd sleep miss | Medium | Catch-up ledger. |
| Graph throttling | Medium | Retry-After/backoff. |
