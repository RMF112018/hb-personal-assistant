# 10 — Text Vault Fail-Closed Hardening Plan (assessment; code change = separate authorization)

## Text Vault fail-open hazard (from N4/N4A)
`security/text_vault.py`: `_key()` silently generates a new key if absent; `decrypt_text` returns `None` on missing
key/blob/`InvalidToken`; no coherence enforcement. Mitigated for the current NAS host (N4A installed real key+blobs),
but the code-level hazard remains for any future bring-up.

## Recommended hardening (implement only when authorized)
1. **Fail-closed on incoherence:** if the DB has encrypted refs and no key file / `HB_TEXT_VAULT_KEY`, refuse to
   auto-generate a key; raise/report instead. Allow generation only in an explicit initialization mode.
2. **Coherence command:** `hb-assistant vault check` (or a readiness probe) — verifies key exists, blob dir exists,
   DB refs ↔ blobs; no decrypt by default; never prints refs. (Promote the N4/N4A count-based check into supported code.)
3. **Clearer decrypt errors:** distinguish key-missing / blob-missing / invalid-token / wrong-key instead of a bare `None`.
4. **Startup preflight:** before production runtime (N8+), fail startup if encrypted refs exist and the Text Vault is incoherent.
5. **Tests:** missing key, missing blob, wrong key, explicit-init allowed, migrated-DB-root fail-closed.

## Related: source-identity hardening (from 04)
Before any multi-root NAS activation (N8): add `source_root_key` to `source_id` (`source_index_repository.py:38`) and
to the unique index (`source_intelligence_tables.py:110`), migration-guarded, to remove the cross-root collision defect.

## This pass
Assessment only. No code changed. Both items gated on explicit code-change authorization.
