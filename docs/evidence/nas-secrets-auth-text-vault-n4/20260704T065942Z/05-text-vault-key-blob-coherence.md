# 05 — Text Vault Key ↔ Blob ↔ DB Coherence

## Source coherence — PROVEN (Mac)
Existence-only check (no blob content read, no decrypt, no refs printed): for each distinct DB ref, tested whether
`<source-app-support>/security/text-vault/<ref>.enc` exists.

| Metric | Value |
|---|---|
| distinct refs in copied DB | 7,198 |
| refs with a matching blob | **7,198** |
| refs missing a blob | **0** |
| blobs on disk (source) | 7,202 |
| orphan blobs (on disk, unreferenced) | 4 (harmless) |
| key file present | yes (`security/text-vault.key`, 44 B, 0600) — a valid Fernet key length |
| **verdict** | **COHERENT** |

⇒ The Mac source is fully coherent. Because plaintext is unrecoverable (see 04), re-provisioning is impossible;
the key + blobs **must be copied** to make the NAS DB usable.

## NAS coherence — DEFERRED
`<app-support>/security/text-vault` is **absent** on the NAS; the key is not present. The NAS DB therefore has
7,198 refs with **no** backing material ⇒ **incoherent on NAS today** (expected — this pass makes no NAS writes).
NAS-side coherence proof is deferred to the authorized copy (spec in 08 / 10).

## Fail-open hazard → FUTURE HARDENING ITEM
Repo-truth (`security/text_vault.py`): `_key()` **silently generates a NEW key** when the key file is absent and
`HB_TEXT_VAULT_KEY` is unset; `decrypt_text` returns `None` on missing key/blob/`InvalidToken`. No code validates
key↔blob↔DB coherence. Consequence: a NAS bring-up that omits the key would mint a fresh key and **silently orphan
all 7,198 bodies**, with callers treating the result as "no body" rather than erroring.

**Recommended hardening (future work, not this pass):** when encrypted refs exist but key/blob material is absent or
a decrypt fails, the runtime should **fail closed or clearly report incoherence** (e.g. refuse to auto-generate a
key when refs already exist; surface a startup/readiness warning; count decrypt failures) instead of silently
generating a new key or returning `None`. This makes the documented "move key+blobs+DB together" invariant
enforceable rather than operator-memory-only.
