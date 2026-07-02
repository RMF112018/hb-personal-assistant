# Future: Operator Classification by Project Identity + Tags (Phase 10L-H)

**Status: NOT implemented in Phase 10L.** This document scopes a future operator-facing classification
workflow. Phase 10L (A+B+C) delivered only DB/vault reconciliation, email archive routing correction,
and README singleton upserts — all tooling + dry-run only. No operator UI/workflow was built.

## Motivation

Deterministic + (future) local-model classification will still leave a residue of sources whose
project identity, document type, or tags need a human decision. Operators need a bounded, auditable way
to make those calls without hand-editing generated cards.

## Scope of the future feature

- **Operator project-identity assignment** — attach a canonical `project_key`/`project_number` to a
  source or duplicate group, overriding weak folder/filename evidence.
- **Operator tag adjustment** — promote a `review/proposed/*` tag (see the dynamic-classifier doc) into a
  production tag, or remove an incorrect one.
- **Document-type confirmation / override** — confirm or correct a deterministic/model `document_type`
  via the existing guarded repair workflow (never a free-form write).
- **Duplicate-group approval** — approve the canonical card for a content-duplicate group (depends on the
  duplicate-collapse grouping layer; see that doc).
- **Graph-relationship approval** — approve/reject proposed `[[links]]` before they are written
  (reuses the Phase 10C/10G/10I review surfaces).
- **Classifier feedback loop** — operator decisions become labeled examples that tune deterministic
  signals and the local-model prompt/threshold.
- **Audit trail** — every operator decision recorded with actor, timestamp, before/after enum, and
  evidence kind; count-only in safe evidence, detail in `local-sensitive/`.
- **Review-queue UX** — a bounded queue of `review_required` sources with one decision per item.

## Guardrails (carried from Phase 10L)

- No operator action may delete source rows or source files.
- All writes stay guarded: dry-run default, backup, exact confirm flags, generated-marker protection.
- Safe evidence stays count-only; identifiers/paths/excerpts live only under `local-sensitive/`.

## Explicit non-goals for Phase 10L

Nothing in this document is built in Phase 10L. It is a design placeholder to be scheduled as a later
phase after the dynamic classifier (10L-F) and duplicate-collapse grouping (10L-D) land.
