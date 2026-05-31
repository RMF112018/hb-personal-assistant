# Phase 07C — Prompt 00: Phase 07B Gap Audit

**Phase:** Construction Intelligence 07C — Document Intelligence Promotion
**Prompt:** 00 — Repo Truth Audit and 07B Gap Inventory
**Generated (UTC):** 2026-05-31
**Baseline:** HEAD `748ed7e6519ada0a74d09376f2d2fe353627ac2b`, schema version `23`, package `1.3.0`.
**Companion:** `00-repo-truth-rebaseline.md` (validation matrix).

> This audit compares the Phase 07B closeout and the 07C planning package against **live repo + local
> store truth**. Repo code/tests/runtime are authoritative over planning notes (per CLAUDE.md governance).
> Leak-safe: counts and identifiers only.

## 1. Summary

Phase 07B is complete and honestly closed for its calendar/email/thread scope. The full Prompt 00
validation matrix is green (see companion). No unsafe 07B closeout or overstated readiness was found:
`meeting_prep_readiness_claim` and `risk_digest_readiness_claim` are both `blocked`, and 07D meeting-prep
is gated with `auto_readiness_allowed=false`.

One package-documentation inaccuracy and a set of genuine, already-disclosed 07C handoff gaps were
identified. None is a 07B safety defect; all are document-intelligence work items for 07C.

## 2. Correction to Package Audit Doc `02_REPO_TRUTH_AUDIT_SUMMARY.md`

The package audit states: *"No implemented `construction_document_cards` table or successor document-card
table exists at schema version 23."*

**Repo truth (authoritative):** the `construction_document_cards` table **does exist** and has since
schema **V5** (`migrator.py` line ~403), with a minimal upsert/get repository in
`construction/store/repositories.py` (`upsert_document_card` / `get_document_card`) and a reference in
`data_quality/gates.py`.

- Live shape (V5 stub): `card_id, source_id, drive_item_id, project_key, document_type, status,
  confidence, needs_review, card_path, created_utc, updated_utc`.
- Live population: **0 rows** — never materialized.

**Reconciliation:** the package's *intent* is correct — no document-card **promotion/population** has
happened, and the stub lacks 07C contract richness (hashed name, classification provenance, extraction
eligibility, relationship candidates, redaction attestation). But the literal "table does not exist"
wording is inaccurate and is corrected here. 07C must **extend/populate** the existing V5 table (or add
additive successor columns/tables), **not** assume a greenfield create. This is the single most important
truth correction for downstream 07C prompts (02 schema/contracts, 04 materialization).

## 3. Confirmed 07C Gaps (open work, not 07B defects)

| # | Gap | Live evidence | Severity | 07C treatment |
|---|---|---|---:|---|
| G1 | Document cards unpopulated | `construction_document_cards` = 0 rows; gate `document_card_population_status = deferred_not_blocking`, `future_phase=07C`, `observed=false` | High | Promote/materialize in 07C (Prompts 02/04). Extend V5 stub additively. |
| G2 | Document-specific review-routing gate absent | gate `review_required_routing_presence = deferred_not_blocking`, `reason=feature_not_yet_implemented` | High | Implement document review routing measured directly (07C). |
| G3 | SharePoint whole-drive vs OneDrive selected-folder scope policy not explicit | scope primitives exist (`source_scope: sharepoint_project_drive_folder`; `policy/inventory_first.py` `ONEDRIVE_INVENTORY_FIRST_SCOPES`) but no explicit "SharePoint=whole-drive nested / OneDrive=selected-folder nested" 07C distinction | High | Encode explicitly in 07C Prompt 03 (refinement of existing primitives, not greenfield). |
| G4 | Raw file fields in lower file layer | `construction_drive_item_inventory` (401 rows) has `name`, `web_url`, `parent_path` all non-null (401/401) | Medium | Never copy raw values into cards/evidence/Obsidian; hash/redact derivatives only; add a copy-prevention proof. |
| G5 | Broad delegated write scopes present (files) | `Files.ReadWrite.All` in configured delegated scopes; `permission_tightening=deferred`; guard self-test: 24 reads allowed / 19 mutations blocked | Medium | Keep disclosed in status/evidence; tighten only on Azure consent change. Endpoint guard already enforces read-only. |
| G6 | Calendar least-privilege deferred | `Calendars.ReadWrite.Shared` present; endpoint guard enforces read-only | Medium | Keep disclosed; do not let it disappear from status/evidence. |
| G7 | Table-inventory contract/live count delta | contract=96 vs live=101; all 96 contract tables `present_in_db=true` | Low / reconcile | Two contract entries (`v_procore_inspection_unanswered_items`, `v_procore_open_action_signals`) are **views**; live count includes 07B-era additions made after the 07A inventory seed. Documentation drift only — refresh the inventory seed when convenient; not a validation failure. |

## 4. Residual Risks Carried Into 07C

- **Least-privilege (G5/G6):** broad file + shared-calendar write scopes are tenant-consented but
  runtime-guarded read-only. Acceptable while disclosed; must remain visible in `status`/`no-writeback`
  evidence and must not be silently dropped.
- **Raw-field leakage surface (G4):** the 401-row inventory is the primary place raw names/URLs/paths
  live. 07C card/classification/relationship/Obsidian layers must consume only hashed/redacted
  derivatives; a no-raw-copy proof should accompany 07C materialization.
- **Metadata-only thread summaries (07B, accepted):** subject-topic candidate signal is unavailable
  from metadata-only summaries. Keep documented; do not weaken privacy posture to recover it.

## 5. Truthfulness Assessment

The 07B closeout is consistent with live implementation: calendar mutation lockout is tested, calendar
project-number matching hashes before persistence, candidates remain candidates (no weak/model-only/
sensitive auto-promotion), `raw_content_leakage_scan` and `external_writeback_scan` both pass, and
07D/08B readiness is correctly blocked. The only documentation defect is the doc-02 "table does not
exist" overstatement corrected in §2. No gate overstates readiness.

## 6. Stop-Condition Check

- No validation command failed unexpectedly — all 13 matrix commands exited 0.
- No mutation endpoint or write scope was required or exercised.
- No evidence required raw content or unsafe identifiers (all summarized as counts).
- No gate or closeout overstated readiness.

→ **No stop condition triggered. 07C may proceed to Prompt 01 (07B Remediation Preflight).**

## 7. Prerequisites for the Next Prompt (Prompt 01 — 07B Remediation Preflight)

1. Treat §2 as binding: 07C document-card work **extends the existing V5 `construction_document_cards`
   table additively** (new migration ≥ V24); it does not create from scratch.
2. Carry G4 forward as a hard constraint: design hashed/redacted card fields before any materialization;
   plan a no-raw-copy proof.
3. Keep G5/G6 residual risks in `status`/no-writeback evidence; do not regress disclosure.
4. Keep G3 as the explicit 07C Prompt 03 scope-policy deliverable (whole-drive vs selected-folder).
5. Re-run the green matrix at the start of any schema/CLI/gate-changing prompt; do not rely on this
   rebaseline once code changes land.

## 8. Leak Scan

Scanned before commit: no raw document text, file names, web URLs, parent paths, signed/download/
tokenized URLs, tokens, secrets, PEMs, raw email bodies, calendar payloads, model prompts/responses,
tenant GUIDs, or UPNs. Counts and table/column identifiers only.
