# Phase 10K — Deterministic Classifier Repair + Source-Type Provenance (evidence)

Repairs the three known-misclassified source-card families (value-analysis logs, generic specification
templates, clarification/question memos) at the deterministic classifier layer and, for already-
generated cards, via a bounded/reversible repair tool. Deterministic-first, no Ollama, no source-file
reads, no new cards, no DB writes.

## Contents
- `00-repo-state.txt` — branch/base/status at start.
- `01-repo-truth-audit.md` — classification pipeline audit.
- `02-classifier-policy.md` — repair policy, families, signal precedence, guards.
- `03-rendering-policy.md` — first-class rendering for the 3 new types.
- `04..09` — per-family targeted dry-runs (VA / spec / memo).
- `10/11` — bounded Tropical dry-run over all generated cards (visibility only).
- `12` — targeted apply of the 3 known cards (safe summary + report).
- `13-targeted-apply-invariants.md` — apply invariants + per-card verification.
- `14-redaction-proof.txt` — safe-evidence leak scan + local-sensitive inventory.
- `15-test-results.txt` — pytest + ruff.
- `16-known-limitations.md`, `17-rollout-checklist.md`.
- `local-sensitive/` — git-ignored: before/after card text, backups, per-card detail rows.

## Headline results
- Bounded Tropical dry-run (103 cards): 3 hard-conflict repairs, 15 review_required, 0 skipped, all
  other cards untouched; invariants 0.
- Targeted apply (3 cards): warranty→value_analysis, submittal→specification_template,
  scope_of_work→clarification_memo; managed blocks + source ID/SHA/timestamps byte-preserved;
  db_mutations 0; idempotent.
