# 06 — Risk Register and Guardrails

## Risk Register

| Risk | Severity | Mitigation |
|---|---:|---|
| Wrong repository audited | High | Starting checks must prove `hb-personal-assistant` remote and HEAD. |
| Docs claim behavior not implemented | High | Code/test/evidence hierarchy controls acceptance. |
| `run morning` silently extracts zero actions | High | Seeded nonzero action proof required. |
| Dry-run writes unexpected business objects | High | Explicit dry-run mutation policy and tests. |
| Obsidian write corrupts user notes | High | Marker-bound tests and user-content preservation proof. |
| `written_to_note` claimed but not persisted | Medium | DB/source-link proof required. |
| Graph consent blocker misclassified | Medium | Taxonomy and evidence must classify admin consent accurately. |
| Validation remains too weak | Medium | Shrink Ruff/mypy exclusions for MVP-critical modules. |
| Sensitive data committed in evidence | High | Run sensitive scan and manually review evidence. |
| App-only runtime workaround introduced | High | Explicit grep + architecture guardrail. |

## Guardrails

- Do not implement Microsoft 365 writeback.
- Do not implement app-only runtime mail/calendar.
- Do not store full email bodies.
- Do not store full file contents.
- Do not log or commit tokens, PEMs, Keychain/cache data, or private source content.
- Do not mutate Obsidian during dry-run.
- Do not mutate `action_items` or `source_links` during dry-run unless explicitly changing the policy and tests.
- Do not broad-refactor unrelated modules.
- Do not re-read files still in immediate context; use targeted greps and precise reads.
