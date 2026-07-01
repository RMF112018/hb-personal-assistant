# Phase 10K — Rendering policy for the three new document types

The three repaired types are first-class across every downstream path (never map to `unknown`).

## `value_analysis`  (tag `source/type/value-analysis`)
- Why This Matters: "A value-analysis log tracks proposed cost, scope, or specification changes for PM
  review and budget/scope alignment."
- PM Review Cues: confirm status of pending/conditional items · verify cost impacts vs the current
  budget/change log · confirm accepted items are reflected in current project documents.

## `specification_template`  (tag `source/type/specification-template`)
- Why This Matters: "A specification template may inform project requirements, but it must be confirmed
  before treating it as a project-specific submittal or contract requirement."
- PM Review Cues: confirm whether the template was adopted · identify applicable sections and any
  project-specific edits · do not treat template language as approved project direction without
  confirmation.

## `clarification_memo`  (tag `source/type/clarification-memo`)
- Why This Matters: "A clarification memo captures open questions or coordination points that may
  require PM follow-up before relying on scope, sequence, or schedule assumptions."
- PM Review Cues: identify which questions remain open · confirm responses, decisions, or follow-up
  owners · tie resolved clarifications back to governing project documents.

## Consistency points updated (all tested)
- `source_notes._PM_GUIDANCE` (why/cues/followup) + `_pm_guidance` dispatch.
- `source_note_graph.CONTENT_TYPE_TAGS` (adds the three slugs) + `_DOCTYPE_CONTENT` (maps types → slugs,
  never `unknown`); `sanitize_tag` accepts the new tags.
- Source Basis / Source Summary "Document type:" line + Source Basis classification reason carry a
  PM-safe Phase 10K provenance note. PM cues contain no forbidden liability language.
