# Phase 10K — Rollout checklist

1. Merge order: Phase 10J (PR #257) must merge first — 10K stacks on it (base d481a042).
2. Tests green: 3 new suites + 10J/obsidian regression (see 15-test-results.txt); ruff clean.
3. Dry-run first on any new scope: `--dry-run` (default) with `--json-output`/`--markdown-report`;
   review `repairs_by_*` + `review_required` + `skips_by_reason`.
4. Apply is bounded + confirmed: `--apply --confirm-classifier-repair --confirm-db-path --confirm-vault-path
   --backup-dir <local-sensitive>` with the backend `:8000` stopped and an empty queue; restart the
   backend faithfully afterward.
5. Apply scope in this phase = the 3 known cards only (`--note-rel` ×3). Do NOT apply the broader
   Tropical corpus in 10K.
6. Verify: re-read repaired cards (type/tag/Why/Cues/Source Basis), confirm managed blocks + source
   ID/SHA/timestamps unchanged, confirm idempotent re-run, confirm invariants 0.
7. Commit `fix(obsidian): repair deterministic source classification provenance`; safe evidence only,
   `local-sensitive/` git-ignored. No push/PR without explicit approval.
8. Follow-up: Phase 10L — expand families + operator review queue for the 15 review_required cards.
