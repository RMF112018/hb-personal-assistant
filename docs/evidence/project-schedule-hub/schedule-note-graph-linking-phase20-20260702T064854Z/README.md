# Phase 20 — Schedule Note Graph Linking

Evidence stamp: `20260702T064854Z`

## Artifacts

| File | Description |
|------|-------------|
| `00-repo-state.txt` | Branch/HEAD/base |
| `01-repo-truth-audit.md` | Boundaries and non-routes |
| `02`–`03` | Phase 19 fixture note generation (seed for graph) |
| `04`–`05` | Graph dry-run JSON + markdown review |
| `06`–`09` | Fixture note before/after graph apply |
| `07`–`08` | Fixture apply + idempotency rerun (`write_attempts=0` on rerun) |
| `10-path-redaction-qa.txt` | Path QA attestation |
| `11-live-vault-apply-blocked.txt` | Live apply blocked without explicit confirmation |
| `12`–`13` | Phase 19 rerun after graph; graph block preserved |
| `16`–`17` | Live vault dry-run (skipped if vault absent) |
| `19-test-results.txt` | Phase 20 + Phase 19 CLI regressions |

## Default operator mode (safe)

```bash
python scripts/obsidian_schedule_note_graph.py \
  --vault-path "$VAULT" \
  --project-key tropical \
  --json-output review.json \
  --markdown-output review.md
```

## Fixture apply (evidence only)

```bash
python scripts/obsidian_schedule_note_graph.py \
  --vault-path docs/evidence/project-schedule-hub/schedule-note-graph-linking-phase20-20260702T064854Z/fixture-vault \
  --evidence-dir docs/evidence/project-schedule-hub/schedule-note-graph-linking-phase20-20260702T064854Z \
  --project-key tropical \
  --apply-links --confirm-graph-apply
```

**Excluded from commit:** `fixture-vault/`, `fixture-phase20.db`, `local-sensitive/`
