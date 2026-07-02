# Phase 10K — Repo-truth audit (classification / source-card / provenance)

Read-only audit of the classification pipeline before implementing 10K. Anchors are file:line in the
Phase 10J base branch (d481a042).

## Where document_type is assigned
- The single deterministic classifier is `source_analyzers.py::from_detail(detail)` (pure; no LLM, no
  file re-read). Signal families are consulted FIRST-MATCH, in priority order: file extension →
  filename tokens/sheet number → path segments → extracted-text keyword ladder (`_doc_type_from_text`).
  An override block (schedule/CAD/blank-submittal/template/eml precedence) runs last.
- `document_type` is NOT stored in SQLite. It is recomputed at card-render time and written to card
  frontmatter via `SourceAnalysis.to_frontmatter_dict()`, then re-read downstream (`NoteFact` →
  `source/type/*` tags + relationship scoring). Repairing an existing card = editing the card file.

## Signal families / weighting
- No weighting — strictly ordered first-match. Title/frontmatter are NOT used for document_type today
  (title signals are the Phase 10J addition `_title_signal`, which 10K promotes to the repair layer).

## Tags / PM cues / Why This Matters / Source Basis
- `source/type/*` tags are added post-hoc by the note-graph layer (`content_tags_for` →
  `_DOCTYPE_CONTENT` → `CONTENT_TYPE_TAGS`); unmapped types fall to `source/type/unknown`.
- Why This Matters / PM Review Cues / Follow-Up are a deterministic per-type map `_PM_GUIDANCE`
  (`source_notes.py`), dispatched by `_pm_guidance(document_type)`; `_review_cues` appends dynamic
  cues from analyzer fields (amount/number/status/project).
- Source Basis renders `Document type: … (deterministic — …)` + `Classification reason:` from
  `SourceValue.reasons` (transient; NOT persisted). Source ID / SHA-256 / Indexed at also rendered.

## Managed blocks (must be byte-preserved)
- `hb-local-summary` (Advisory Summary), `hb-project-identity` (authoritative identity),
  `gc-graph-links`, `hb-email` / `hb-email-attachment` / `hb-email-attachments`. Every block is a
  single `<!-- prefix:start … --> … <!-- prefix:end -->` pair spliced in place.

## Safe way to repair a misclassified card
- Edit only within the frontmatter fence (document_type + source/type tag) and the deterministic
  section bodies (Source Summary type line, Why This Matters, PM Review Cues, Source Basis type/reason),
  reproducing them via the real renderer helpers (`_source_summary`/`_review_cues`/`_pm_guidance`).
  Never cross a `<!-- … -->` marker; never touch source ID/SHA/path/timestamps or manual content.
- Reuse the existing controlled dry-run/apply harness: `cg._select` (bounded Tropical),
  SHA-gated `create_note`, backup→write→rollback, `_db_fingerprint`/`_queue_counts` invariants,
  count-only `-safe` evidence + git-ignored `local-sensitive/`.

## Classifier-conflict persistence
- Conflicts were only *counted* during 10J summary generation (`detect_classification_conflict`), never
  persisted or repaired. 10K promotes that detection to a guarded deterministic repair.
