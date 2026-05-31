# 39 — Phase 07C: Obsidian Document Outputs (registers + review notes)

**Phase:** 07C (Document Intelligence Promotion) — Prompt 10.
**Status:** Implemented; live evidence is a **dry-run preview** (the user's real Obsidian vault was not written).
**Evidence:** `docs/evidence/construction-intelligence-phase-07c-document-intelligence/10-obsidian-output-preview.md`.

Projects the V24 document intelligence (cards + classification / project-match / relationship candidates +
extraction dispositions + the Prompt-09 project preview) into **grouped, marker-bounded** Obsidian notes — never
one note per document. Read-only, counts-only, output-fenced. No schema change (`LATEST_SCHEMA_VERSION` stays 24).

## Register / review structure

`construction/document/obsidian_projection.py` `DocumentObsidianProjector(store).project(*, project_key=None,
dry_run=True)`, mirroring `FileObsidianProjector` (grouped `_DocArtifact`s + idempotent marker `_write_artifact`
+ build-time `_assert_output_fence` + dry-run default). Scope is the projects that already have a review-controlled
preview (`store.list_document_intelligence_previews`, added this prompt). Per project it re-derives counts from
`list_document_cards` / `list_document_classification_candidates` / `list_document_relationship_candidates`
(grouped by `document_card_id → project_key`) and parses the preview's `warnings_json`, then builds **two** notes:

- **Document Register** (`{_BASE}/Projects/{pk}/Document Register.md`, marker `HB-DOCS-DOCUMENT_REGISTER`):
  frontmatter (type, project_key, source, confidence_class, read-only attestations) + counts by document type /
  confidence class / extraction eligibility / review status + relationship candidates by record type + the
  preview's warnings + a source reference + a Guardrails section.
- **Document Review** (`{_BASE}/Review/{pk} Document Review.md`, marker `HB-DOCS-DOCUMENT_REVIEW`): documents +
  candidate items pending review, review-required counts by category (classification / relationship / manual
  extraction approval / unclassified backlog), routed to the review queue (not inlined), + Guardrails.

`_BASE = "Work/HB Personal Assistant/07C_Document_Intelligence"`; writes resolve under
`PathPolicy().get_vault_root()`. The output fence bans tokens/signed-or-download/delta URLs, auth material, PEM
blocks, full-text markers, **and any `http(s)://`** (the document register has no legitimate URL), so a render
carrying a raw link fails before any write. Marker writes are idempotent (DOTALL regex replace between the
START/END comments; markers stay singular on re-apply). Surfaced by
`hb-assistant graph files document-obsidian [--project] [--dry-run/--apply] --json` (dry-run default).

## Live result

Live **dry-run preview** (`graph files document-obsidian --json`): 1 project (`tropical`), `notes_planned=2`
(register + review), `notes_written=0`; both would-be vault paths absent (vault untouched). The rendered register
shows 283 documents (classified 67 / unknown 216), the document-type / confidence / extraction / review-status /
relationship counts, the preview's warnings, and `confidence_class=weak_heuristic`; the review note shows 283
documents + 261 candidate items pending (classification 238, relationship 23, manual-approval 273, unclassified
backlog 216). Determinism verified identical summary across `PYTHONHASHSEED` 1/2/3. A leak-scan of the rendered
notes found 0 forbidden-marker / URL / email / raw-name hits. Gates unchanged: `document_card_population_status`
pass; `raw_content_leakage_scan` / `external_writeback_scan` / `graph files no-writeback-proof` green;
`meeting_prep_readiness.ready` stays **False**.

## Guardrails / deferrals

No one-note-per-document (`one_note_per_document=False`); grouped register + review only. No raw document text /
full paths / names / URLs / tokens / secrets / delta links — output-fenced at build and write time, and the
rendered output is leak-scanned. Marker-bounded, idempotent, reproducible; includes confidence labels, review
status, warnings, and source references. No external-system writeback; SQLite read-only, no Graph/Procore call; no
source files copied to vault. No card mutation; no auto-promotion; no high-impact conclusion. The live evidence is
a **preview** — the projector supports `--apply` to write the marker-bounded notes, exercised by tests against a
tmp vault, but the user's real vault was not written. The V24 satellite tables remain outside the
no-writeback-proof static-scan scope (deferred to Prompt 12; not claimed here). The Phase 07C data-quality gate
suite (11) and the no-writeback / no-secret / no-raw-text proof extension over the V24 tables (12) remain deferred.
