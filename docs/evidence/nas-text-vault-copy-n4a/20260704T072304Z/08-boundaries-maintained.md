# 08 — Boundaries Maintained

## Authorized writes performed (only these)
- Created `<app-support>/security/text-vault/` (operator sudo).
- Copied `text-vault.key` → `<app-support>/security/text-vault.key`.
- Copied 7,202 `.enc` blobs → `<app-support>/security/text-vault/`.
- Set ownership/perms (svc:users; dirs 700; key/blobs 600).
- Placed + removed a bounded NAS temp tar and a temp coherence helper.

## Negative scope — proven NOT done
| Boundary | Held? | Evidence |
|---|---|---|
| No backend start | ✔ | nothing launched |
| No MCP start | ✔ | not invoked |
| No scheduler / watcher / ingestion | ✔ | none |
| No Obsidian card-gen / vault migration / source-root migration | ✔ | none |
| No Cloudflare / firewall / router / Tailscale change | ✔ | none |
| No direct svc SSH restored | ✔ | all SSH as bfetting; svc accessed only via `sudo -u` |
| No broad passwordless sudo | ✔ | operator interactive sudo, bounded to extract/chown/chmod within `security/` |
| Copied NAS DB never opened writably | ✔ | all DB access `mode=ro`; `apply()` never called; main-file size/mtime = N3 |
| No secret/key/decrypted content printed or committed | ✔ | metadata/counts only; `sudo cat` on key never used; refs never printed |
| No push / no PR | ✔ | see 10 |

## Temp cleanup
Local tar removed; NAS temp tar removed; coherence helper removed; NAS `<app-support>/tmp/` confirmed free of `n4a`
artifacts. No key material remains outside `<app-support>/security/` (NAS) and the Mac source.
