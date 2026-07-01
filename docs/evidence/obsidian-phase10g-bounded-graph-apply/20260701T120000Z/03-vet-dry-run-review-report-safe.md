# Phase 10G — Bounded Note-Graph Apply — Review Report (safe / count-only)

- mode: dry-run
- eligibility_mode: primary_secondary
- project_number: 23-435-01
- project_key: tropical
- procore_project_id: 2525840

## Selection
- notes_selected: 103 (project=91, email=10, attachment=2)
- selection_truncated: False
- excluded_outside_project: 25

## Candidates (deterministic basis — NOT applied relationships)
- candidate_pairs: 4
- lineage_pairs_excluded: 0
- duplicate_review_candidates (same-content, review-only): 0
- candidate_basis_counts: same_document_number: 2, same_document_type: 3, same_email_domain: 1, same_parent_email: 1, same_participant: 1, same_procore_id: 4, same_project_alias: 1, same_project_key: 4, same_project_number: 3, same_subject_normalized: 1, same_thread_topic: 1, shared_title_phrase: 3

## Vetting (local qwen2.5:14b, advisory)
- ollama_calls: 4
- vetted_pairs: 4
- approved_pairs: 1
- rejection_reasons: rejected: 3

## Applied (qwen-approved relationships — separate from basis)
- relationships_applied: 1
- reciprocal_links_applied: 2
- applied_relationship_types: same_project: 1
- notes_modified: 2
- tags_added: 8
- backlink_integrity_passed: None (verified=0)

## Invariants
- queue_delta: 0
- db_mutations: 0
- created: 0, deleted: 0
