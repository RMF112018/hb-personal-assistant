# Canonical Artifact Promotion Workflow (N8C-23)

Promotion is the one point where a draft becomes a canonical record and a vault card. The trust model
is designed so a connected client can never promote on its own authority: it can only *ask*, and the
server only acts on its own recorded evidence.

## Three server-owned trust primitives

1. **Server-minted `operator_approval_id`.** A client never invents or supplies an approval id.
   `pa_artifact_proposal_review(decision="approve")` records a `pa_artifact_review_decisions` row and
   mints an approval id bound to the proposal + bundle. `pa_artifact_promotion_validate` then binds
   the set of approved proposals to a bundle-level `operator_approval_id`. Promotion looks it up
   server-side and rejects any mismatch (`operator_approval_mismatch`).

2. **Validation receipt binds the exact plan.** `pa_artifact_promotion_validate` computes a
   `validation_hash` over the canonical tuple of
   `{promotion_bundle_id, sorted approved proposal ids, proposed canonical ids, proposed vault paths,
   tags, backlinks, per-proposal content hashes}` and persists a `pa_artifact_validation_receipts`
   row. `pa_artifact_promotion_apply` requires that receipt and **recomputes the hash before writing**.
   If anything changed since validation (e.g. another proposal was approved), the recomputed hash no
   longer matches and apply fails closed with `revalidation_required`.

3. **Server-derived idempotency.** The idempotency key is
   `sha256(promotion_bundle_id + validation_hash + operator_approval_id)[:24]`. A client-supplied key
   is accepted only if it equals the server-derived value; otherwise `idempotency_key_mismatch`. A
   repeated apply with the same key short-circuits and returns the original receipt — no duplicate
   rows, no duplicate cards.

## Apply write order (fail-safe)

```
1. validate: existing receipt for idempotency key?  → return it (idempotent reuse)
2. check operator_approval_id matches the bundle     → else operator_approval_mismatch
3. recompute validation_hash                          → else revalidation_required
4. PHASE 1 (DB txn): insert pa_canonical_artifacts at status=needs_materialization_repair,
                     pa_artifact_links, pending pa_promotion_receipts; proposals → promoted
                     (INSERT OR IGNORE — safe on retry)
5. PHASE 2 (per artifact): resolve path → render + redact → atomic create_note
       success → status=canonical + vault_path
       failure → keep needs_materialization_repair, mark promotion_partial_failure,
                 add pa_artifact_repair_tasks row
6. PHASE 3: write receipt card to 99 System/Receipts, update canonical manifest
            (99 System/Manifests/canonical-artifact-manifest.{md,json}), finalize receipt + bundle
```

DB rows are written before any card, so a crash mid-materialization is recoverable: the canonical row
exists in `promotion_partial_failure` with a repair task, and re-running apply is idempotent.

## Statuses

- Canonical: `needs_materialization_repair → canonical | promotion_partial_failure`.
- Receipt: `pending → promoted | partial_failure`.
- A `partial_failure` promotion returns a receipt that lists which artifacts materialized and which
  need repair; the canonical rows remain queryable for a later operator-run repair.

## What promotion never does

No canonical deletion. No raw SQL. No writes outside the vault root. No new top-level vault folder. No
external write-back. No silent promotion — every canonical record traces back to a recorded operator
approval and a bound validation receipt.
