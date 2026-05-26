# 10 — Risk Exposure

## P0 Risks

| Risk | Exposure | Mitigation |
|---|---|---|
| Misclassifying admin consent as code failure | Wasted implementation churn and false negative acceptance. | Formal blocker taxonomy and proof commands. |
| Misclassifying DNS as active after consent context changed | Trust/evidence failure. | Correct stale docs and require fresh command evidence for DNS. |
| Persisting full email bodies | Privacy/security violation. | In-memory bounded inspection only; tests and sensitive scan. |
| Persisting full file contents | Privacy/security violation. | Parser excerpts only; no full text storage. |
| Microsoft 365 writeback added accidentally | Scope expansion and safety breach. | Read-only Graph clients and mutation lockout tests. |
| App-only token used for runtime mail/calendar | Design/security violation. | Token classifier enforcement and proof tests. |

## P1 Risks

| Risk | Exposure | Mitigation |
|---|---|---|
| Duplicate action items | User loses trust in brief/action intelligence. | Stable keys and idempotent upsert tests. |
| Weak action extraction quality | Noise in daily brief. | Confidence thresholds, monitor category, source maps. |
| Obsidian writer overwrites user content | Data loss. | Marker-bounded tests with user-content preservation fixtures. |
| Morning run fails entirely when Graph is consent-blocked | No local value while consent pending. | Consent-aware stage skipping and local fixtures. |
| Broad Ruff/mypy exclusions hide defects | Low confidence quality gate. | CI plus gradual scope tightening. |

## P2 Risks

| Risk | Exposure | Mitigation |
|---|---|---|
| Ollama unavailable | Semantic features degrade. | Deterministic fallback; do not require Ollama for acceptance. |
| Evidence artifacts leak paths or sensitive strings | Public repo safety. | Redacted evidence writing and sensitive scan. |
| CLI JSON shape drifts | Automation instability. | Contract tests for CLI outputs. |
| Local fixture drift | False confidence. | Keep fixtures minimal and tied to schema contracts. |

## Required Risk Controls

- Sensitive scan after every prompt that touches output/evidence/security.
- Dry-run before apply for any command that can write local state or Obsidian files.
- Evidence artifacts must be redacted and committed only when safe.
- Every P0 risk must have at least one automated test or documented proof.
