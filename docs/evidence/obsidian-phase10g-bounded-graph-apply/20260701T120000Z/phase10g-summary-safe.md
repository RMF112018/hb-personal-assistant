# Phase 10G — Bounded Note-Graph Apply — Closeout (count-only, safe)

> NOTE: the single `same_project` link recorded below was later found INCORRECT (it linked two duplicate
> email cards) and was REMOVED in the correction/audit pass — see `phase10g-correction-summary-safe.md`.
> This file is retained as the original apply record.


Bounded apply of the local note graph over the single Tropical project's Work-domain source cards
(project 23-435-01 / key tropical / procore 2525840), including email + attachment source cards.
Local qwen2.5:14b vet-only; deterministic reciprocal `gc-graph-links` links + controlled tags.
No source-file read, no scan, no new cards/summaries/attachment-extraction, no cloud model,
no queue drain, no DB/runtime-JSON mutation. Backend on :8000 was stopped for the run and restarted.

## Selection (bounded)
- notes_selected: 103  (project 91, email 10, attachment 2)
- excluded_outside_project: 25
- eligibility_mode: primary_secondary (>=1 strong PRIMARY signal AND >=1 further strong signal;
  project signals are secondary/context only, never sufficient alone)
- selection_truncated: false

## Candidates (deterministic basis — NOT the applied relationship)
- candidate_pairs: 4
- lineage_pairs_excluded: 0   (no direct parent-email<->its-own-attachment pairs among candidates)
- duplicate_review_candidates: 0   (no same-content sha-only pairs)
- candidate_basis_counts: same_document_number 2, same_parent_email 1, same_thread_topic 1,
  same_subject_normalized 1, same_participant 1, same_project_alias 1, same_procore_id 4,
  same_project_key 4, same_project_number 3, + weak (same_document_type 3, shared_title_phrase 3,
  same_email_domain 1)  [basis signals only; not applied relationship types]

## Vetting (local qwen2.5:14b, advisory)
- ollama_calls: 4  ;  vetted_pairs: 4
- approved_pairs: 1  ;  rejection_reasons: rejected 3
- post-vet checkpoint: --confirm-apply-approved-count 1 matched the vetted approved count (1)

## Applied (qwen-approved; reported separately from basis)
- relationships_applied: 1
- reciprocal_links_applied: 2   (both directions; verified reciprocal both ways)
- applied_relationship_types: same_project 1
- notes_modified: 2  ;  tags_added: 8
- backlink_integrity_passed: true  (backlinks_verified: 1)

## Invariants
- created: 0  ;  deleted: 0
- queue_delta: 0  ;  db_mutations: 0  (DB metadata fingerprint unchanged across the write)
- rollback bundle: 2 card backups captured before writing (local-sensitive/, untracked)
- vault: exactly 2 cards now carry a single gc-graph-links block; no other cards changed

Detailed per-note rows + rollback bundle live under local-sensitive/ and are never committed.
