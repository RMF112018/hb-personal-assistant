# Phase 09 — Embedding/Vector Policy No-Raw Proof

- proof_passed: True
- generated_utc: 2026-06-04T20:58:37.654131+00:00
- policy_version: phase_09_embedding_vector_policy_v1
- embeddable_family_count: 7

## Candidate validation cases

- [ok] safe_candidate: expected_rejected=False rejected=False violations=0
- [ok] excluded_family: expected_rejected=True rejected=True violations=1
- [ok] non_embeddable_family: expected_rejected=True rejected=True violations=1
- [ok] raw_body_field: expected_rejected=True rejected=True violations=1
- [ok] signed_url_field: expected_rejected=True rejected=True violations=1
- [ok] vector_blob_field: expected_rejected=True rejected=True violations=2
- [ok] secret_shape_value: expected_rejected=True rejected=True violations=1
- [ok] missing_metadata: expected_rejected=True rejected=True violations=1
- [ok] unresolved_review: expected_rejected=True rejected=True violations=1

## Persistence rules

- sqlite_metadata_only: True
- raw_vector_content_persisted: 0
- vectors_persisted_outside_sqlite: True
- no_raw_text_column: True
