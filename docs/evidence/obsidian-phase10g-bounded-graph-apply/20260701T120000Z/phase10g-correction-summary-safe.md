# Phase 10G — Correction / Audit Pass — Closeout (count-only, safe)

## What the original 10G apply got wrong
The first bounded apply wrote ONE reciprocal `gc-graph-links` relationship between two effectively
DUPLICATE email source cards and labeled it `same_project` (confidence 1.00). Wrong because: (a) the pair
is the same source (same content SHA / same email message-id) and must be review-only, not durably linked;
(b) `same_project` is context/secondary evidence, never a durable relationship; (c) the bounded
primary+secondary rule still admitted the pair because it also shared thread/subject/participant primaries.

## Engine corrections (prevent recurrence)
- New DUPLICATE signals `same_source_sha256` (content_sha256) + `same_message_id_hash` (hb-email block),
  joined with `same_attachment_sha256` in DUPLICATE_SIGNALS.
- Duplicate evidence now VETOES durable candidacy even when the pair also shares thread/subject/
  participant/project (mode=primary_secondary).
- Review-only relationship types `potential_duplicate`, `same_source_duplicate`, `same_email_duplicate`,
  and `same_project` are all OUTSIDE APPLY_TYPES → validate_vet rejects them for durable apply.
  `same_project` is a STRICT reject: no durable link and no tag.

## Live correction applied (backend down; unsandboxed; deterministic; no vetting)
- Offending durable links removed: 1 pair (reason banned_type:same_project) — entry-level removal on BOTH
  sides; both blocks emptied → blocks removed; graph tags (related/*, review/qwen-vetted) stripped on the
  2 cards (the duplicate link was their only graph relationship). offending_links_remaining = 0 (no
  one-way link).
- Email-card identity reconciled: 10 Tropical Work EMAIL source cards (defined by the hb-email block —
  NOT the drift-prone analyzer document_type). frontmatter project_key "23-435-01" → "tropical",
  project_number "23-435-01", one project/23-435-01 tag, visible "no project record linked yet" replaced,
  the hb-project-identity block (authoritative) preserved byte-for-byte.
- Invariants: db_mutations 0; queue_delta 0; created 0; deleted 0; no source-file read; no new cards.

## Post-correction verification
- gc-graph-links blocks remaining in Source Notes/Work/: 0.
- Email source cards (hb-email block): 10/10 consistent (frontmatter == identity block, no placeholder).
- Standard applier re-run (dry-run + vet): candidate_pairs 4 → 3 (the duplicate pair is now excluded and
  counted as a duplicate_review_candidate), approved_pairs 0, would-add 0 — a clean no-op; no durable link
  is re-applied. duplicate_review_candidates across the set: 28.

## Scope discipline + findings (NOT fixed — out of the approved email-only scope)
- During apply an initial over-scope (the live analyzer mislabels 6 non-email cards as document_type
  "email") modified 6 NON-email cards; these were REVERTED to their pre-correction bytes, and the scope
  gate was changed to require an hb-email block. Net identity change = the 10 genuine email cards only.
- The same frontmatter `project_key` = "23-435-01" vs block "tropical" disagreement exists CORPUS-WIDE:
  ~91 non-email Tropical Work cards still disagree (a pre-existing 10D/10E generation defect, not created
  by 10G). Out of scope for this email-only correction — recommend a follow-up pass to reconcile all
  Tropical source cards (project + attachment), not just email.

Detailed per-note rows + rollback bundle live under local-sensitive/ (never committed).
