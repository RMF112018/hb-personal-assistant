# 02 — Source Text Vault Revalidation

Source app-support root resolved via config truth (`PathPolicy().get_app_support()`), not assumption; sensitive
absolute path withheld from committable evidence (recorded as `<source-app-support>`; full path in N3/N4 local-sensitive).

## Source materials (metadata only — no key contents, no refs printed)
| Item | Result |
|---|---|
| key `<source-app-support>/security/text-vault.key` | exists; mode 600; owner user:staff; size 44 (valid Fernet key length) |
| vault dir `<source-app-support>/security/text-vault` | exists; mode 700 |
| source blob count (`*.enc`) | 7,202 |

## Coherence (existence check; refs are one-way hashes, not printed; no decrypt)
Reads the sha-verified local DB copy `mode=ro` (see 06 for the local↔NAS linkage), then tests each distinct ref for
a matching `<ref>.enc` on the source.

| Metric | Value |
|---|---|
| distinct refs in DB | 7,198 |
| refs with matching blob | 7,198 |
| refs missing blob | 0 |
| blobs on disk | 7,202 |
| orphan blobs (unreferenced) | 4 (harmless) |
| verdict | **COHERENT** |

Identical to the N4 result ⇒ source unchanged; safe to transfer.
