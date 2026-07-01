# Phase 10I Graph Review Report (safe / count-only)

## Scope
- mode: review
- cards_checked: 103

## Runtime Preconditions
- db_mutations: 0
- queue_delta: 0
- runtime_json_mutated: False
- cards_modified: 0
- ollama_calls: 0

## Corpus Summary
- cards_checked: 103

## Identity Quality
- identity_consistent: 103
- identity_inconsistent: 0
- ambiguous_identity_blocks: 0
- missing_identity_blocks: 0
- non_tropical_in_selection: 0

## Existing Graph Integrity
- graph_blocks: 0
- relationships: 0
- reciprocal_pass: True
- one_way_links: 0
- duplicate_entries: 0
- invalid_relationship_types: 0
- durable_same_project_links: 0
- durable_duplicate_links: 0
- invalid_tags: 0

## Duplicate Review Inventory
- duplicate_review_pairs: 28
- same_source_sha256_pairs: 28
- same_email_message_id_pairs: 1
- same_attachment_sha_pairs: 0
- duplicate_clusters: 4
- largest_cluster_size: 7
- clusters_size_2: 1
- clusters_size_3_to_5: 2
- clusters_size_6_plus: 1

## Relationship Candidate Review
- candidate_pairs: 5225
- primary_secondary_eligible: 3
- weak_only_rejected: 0
- project_only_rejected: 5178
- would_require_human_review: 5225
- candidate_basis_counts: same_document_number: 2, same_document_type: 506, same_email_domain: 44, same_parent_email: 1, same_participant: 44, same_procore_id: 5225, same_project_alias: 44, same_project_key: 5225, same_project_number: 5022, shared_title_phrase: 82

## Isolated High-Value Cards
- isolated_cards: 103
- isolated_high_value_cards: 66
- isolated_email_cards: 10
- isolated_attachment_cards: 2
- isolated_submittal_or_rfi_cards: 2

## Operator Control Design
- future_actions (Phase 10J; executed_in_10i: false): duplicate: mark_duplicate, mark_not_duplicate, choose_canonical, defer, merge_later, delete_later; identity: mark_identity_verified, mark_identity_wrong, request_reconcile; relationship: accept_relationship, reject_relationship, defer_relationship, rollback_relationship, explain_relationship; rollback: preview_rollback, apply_rollback, export_rollback_bundle

## Recommended Next Actions
- Phase 10J: implement operator actions (accept/reject queue, duplicate-cluster decisions,
  explicit rollback, project graph dashboard) driven from these read-only surfaces.

## Guardrails Verified
- cards_modified: 0, db_mutations: 0, queue_delta: 0, runtime_json_mutated: False, ollama_calls: 0
