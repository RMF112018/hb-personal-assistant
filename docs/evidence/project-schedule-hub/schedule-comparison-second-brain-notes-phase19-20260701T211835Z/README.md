# Phase 19 — Schedule Comparison Second-Brain Notes

Evidence stamp: `20260701T211835Z`

## Artifacts

| File | Description |
|------|-------------|
| `00-repo-state.txt` | Branch/HEAD (includes Phase 18A base) |
| `01-repo-truth-audit.md` | Reuse points and boundaries |
| `04`–`07` | Dry-run project/portfolio note JSON + markdown |
| `08-idempotency-proof.txt` | Stable idempotency key sample |
| `09-redaction-proof.txt` | `find_redaction_leaks` on payloads/markdown |
| `10-language-qa-proof.txt` | `validate_rendered_text` results |
| `11`–`13` | Vault safety, LLM gating, advisory validation |
| `14`–`16` | Fixture vault write + rerun idempotency |
| `15-fixture-vault-generated-note.md` | Sample generated note |
| `17`–`18` | Live DB dry-run JSON + portfolio note preview |
| `19-test-results.txt` | Phase 19 + regression tests |
| `20-known-limitations.md` | Residual limits |
| `21-rollout-checklist.md` | Rollout steps |

## Default operator mode (safe)

```bash
python scripts/obsidian_schedule_review_notes.py \
  --db-path "$DB" \
  --vault-path "$VAULT" \
  --project-key tropical \
  --note-type schedule_update \
  --as-of 2026-07-03
```

## Fixture capture

```bash
python docs/evidence/project-schedule-hub/schedule-comparison-second-brain-notes-phase19-20260701T211835Z/capture_phase19_evidence.py
```

**Excluded from commit:** `fixture-phase19.db`, `fixture-vault/`, `local-sensitive/`
