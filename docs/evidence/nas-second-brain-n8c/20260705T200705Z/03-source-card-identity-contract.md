# 03 — Source/Card Identity Contract (proof)

Deliverable: `docs/architecture/n8c-source-card-identity-contract.md`.

Required-content coverage:

| Required | Contract §  |
|---|---|
| Source identity model (source_id, root_key, digest, deleted) | §2 |
| Card identity model, separate from source (computed `card_id`) | §3 |
| source→card / card→source linkage (ambiguity-aware reverse) | §4 |
| Stale rules (deleted/missing/mismatch/version/digest; legacy distinct) | §5 |
| Duplicate rules (one-source-many-paths, cross-source) + card states | §6 |
| Note-type classification (no misclassification) + validation | §7 |
| `.eml` raw/archive/card three-surface model (not blocked) | §8 |
| User-authored Obsidian note policy | §9 |
| Boundaries (read-only, no migration, no write surface) | §10 |

Card identity is **computed** (`compute_card_id`), never stored — so no card-rendering byte change and
no schema migration. All contract behavior is proven by `tests/test_obsidian_source_card_identity.py`
(`10-tests.md`).
