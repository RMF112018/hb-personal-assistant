# 13 — Acceptance Criteria and Closure Checklist

## Phase 14 Acceptance Criteria

### Documentation / Evidence

- [ ] README no longer incorrectly states DNS is the active blocker unless fresh evidence proves DNS.
- [ ] Architecture index reflects admin-consent blocker status.
- [ ] Final evidence contains blocker taxonomy and current classification.
- [ ] All prompt evidence is committed and sanitized.

### Action Intelligence

- [ ] `hb-assistant actions extract --dry-run --json` exists and runs.
- [ ] Action extraction is deterministic and fixture-testable.
- [ ] Stable keys prevent duplicates.
- [ ] Persisted actions have source links.
- [ ] Completed actions are preserved.
- [ ] Waiting-on and review/approval/follow-up signals are tested.

### Workstream Context

- [ ] Context builder includes action items, waiting-on items, file review, meeting prep, body mentions, and retrieval hits.
- [ ] Context results include source IDs/source links.
- [ ] Context can build without delegated Graph consent using local persisted data/fixtures.

### Obsidian Output

- [ ] Marker-bounded writes preserve user content outside markers.
- [ ] Dry-run writes no file and no DB mutation.
- [ ] Apply mode writes note and records/updates `written_to_note` provenance or reports a repo-truth-compatible equivalent.
- [ ] Source map is present in generated brief.

### Morning Orchestration

- [ ] `run morning --dry-run --json` executes local stages even when Graph proof is consent-blocked.
- [ ] Stage statuses are structured and stable.
- [ ] Run ledger is updated appropriately.
- [ ] Sanitized evidence is emitted.

### Security / Privacy

- [ ] No Microsoft 365 writeback paths added.
- [ ] No full email bodies persisted.
- [ ] No full file contents persisted.
- [ ] App-only runtime mail/calendar use remains rejected or impossible.
- [ ] Sensitive scan is clean.

### CI / Quality

- [ ] CI workflow exists and runs safe local-only checks.
- [ ] Test suite passes locally.
- [ ] Ruff passes under the current scoped standard without expanding exclusions.
- [ ] Mypy passes under the current scoped standard without expanding exclusions.

## Final Local Acceptance Classification

When all local criteria pass but Microsoft delegated proof remains consent-blocked:

```text
PHASE_14_LOCAL_ACCEPTED_WITH_EXTERNAL_ADMIN_CONSENT_BLOCKER
```

## Full Acceptance Classification

Only after delegated Graph proof passes post-consent:

```text
ACCEPTED_WITH_DELEGATED_GRAPH_PROOF_COMPLETE
```
