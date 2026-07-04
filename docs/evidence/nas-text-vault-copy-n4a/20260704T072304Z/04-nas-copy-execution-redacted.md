# 04 — NAS Copy Execution (redacted transcript summary)

## Non-privileged half (agent, bfetting)
| Step | Result |
|---|---|
| Build `ustar` bundle (key + 7,202 `.enc`) | 9,994,240 bytes; 7,204 entries (1 key + 1 dir + 7,202 `.enc`); 0 pax |
| Stream to NAS temp tar (0600 bfetting) | transfer ok; size 9,994,240; SHA-256 **match** local↔NAS; GNU-tar entry count 7,204 |
| Stage coherence helper to NAS temp | ok (0644 bfetting; stdlib-only, no decrypt) |
| Remove local tar | removed (key-sprawl reduction; NAS copy already sha-verified) |

## Privileged half (operator, interactive sudo)
Transcript (operator-provided; no key contents / no refs / no decrypted text):
- Guard: no pre-existing `text-vault.key` or `text-vault/` — **passed**.
- Extracted Text Vault material into `app-support/security`.
- `chown personal-assistant-svc:users` + `chmod` applied: `security/` 700, `security/text-vault/` 700, key 600, blobs 600.
- Temp tar removed; coherence helper removed.
- Post-copy: `key: mode=600 owner=personal-assistant-svc:users size=44`; `blob_count=7202`.

## Cleanup verified (agent, read-only)
NAS `<app-support>/tmp/` has no `n4a` leftovers; `security/` is `700 svc` (bfetting cannot traverse — correct
lockdown); copied DB main file metadata unchanged (`size` = N3, `mtime` = N3 placement).

No key contents, blob contents, refs, or decrypted text were printed at any step.
