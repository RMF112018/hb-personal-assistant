# N2 · 08 — Secrets / Text-Vault Migration Plan (PLAN ONLY — no secrets copied)

No secrets, tokens, keys, or encrypted blobs were read, copied, or printed in N2. This is planning only.

## Hard precondition

NAS `auth/`, `security/` runtime trees are **still 0777 / not hardened** (N1D). **Secrets remain
prohibited** until those ACLs are hardened and re-verified. Any secret migration is blocked on that gate.

## MSAL token caches

- Prefer **re-authentication on the NAS** (delegated device-login flow) over copying the macOS token
  cache — cleaner trust boundary, no cache-format/keyring assumptions.
- If a controlled migration is ever chosen, it happens **only after** auth/security hardening, with
  permissions verified before and after, and never printed.

## Procore

- macOS Keychain does not exist on DSM. Re-provision Procore via the app's env/service-credential
  strategy (whatever the repo supports at execution time) rather than copying Keychain material.

## Text Vault (key + blobs + DB coherence)

- DB rows may reference `encrypted_full_text_ref`. The **Text-Vault key, the encrypted blobs, and the
  DB must stay coherent** — migrating one without the others breaks decryption.
- Key/blobs must **not** be copied until auth/security hardening is confirmed. When copied later,
  verify permissions before and after, and keep key/blob/DB from the same consistent point in time.
- Do **not** rotate the Text-Vault key during the initial DB migration unless a rotation is separately
  planned — rotation mid-migration risks orphaning `encrypted_full_text_ref` rows.

## Evidence redaction (mandatory)

Never print token values, key material, or decrypted content in any evidence file. Never include
file paths that reveal secret locations beyond the already-public app-support layout.

## Rollback

Preserve original key/blob state untouched. The DB source is opened read-only; secrets are not touched
in the DB-copy step at all.
