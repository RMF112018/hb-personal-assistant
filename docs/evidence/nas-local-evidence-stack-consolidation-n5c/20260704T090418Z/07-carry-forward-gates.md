# 07 — Carry-Forward Gates

## Resolved gates
| Gate | Resolved by |
|---|---|
| NAS DB placement | N3 (copied DB placed, integrity/schema-98/svc-RO validated) |
| Text Vault coherence on NAS | N4A (key+7202 blobs copied; 7198/7198 refs coherent; re-confirmed unchanged in N5C `06`) |
| Vault mirror to NAS | N5A (221 files / 155 md, svc-readable, least-privilege perms) |
| NAS path availability from scratch context | N5B (svc read + stat-only probe + scratch root) |
| `syn-work` read-only filesystem enforcement | N5B ACL follow-up (svc `r-x` ACE + proven write-denial) |

## Remaining gates
| Gate | Owner phase | Notes |
|---|---|---|
| Auth re-provision (MSAL/Graph + Procore) | **N5C planned; proof only if separately authorized** | see `08` |
| Text Vault fail-closed hardening | code-change phase (separate auth) | refuse silent new-key generation; startup preflight |
| `ExternalSourceRoot.read_only` schema/runtime support | code-quality / activation hardening | FS/ACL currently backstops read-only (N5B); schema field is a follow-up |
| `source_id` omits `source_root_key` | activation / N8 hardening | fix identity key + unique index before any multi-root activation |
| Linux scheduler / operator tooling | N6 / N8 | replace macOS `launchd` |
| MCP-on-NAS via SSH launcher | N7 | bearer/public-URL off by default |
| Watcher / scheduler activation | N8 | gated by identity fix + scheduler + Text Vault preflight |
| Cloudflare Access | N8A | not before controlled activation |
| Full cutover rehearsal | N9 | |
| Production cutover | N10 | |
| Rollback drill / monitoring | N11 | |

## Redaction-maintenance item (optional, non-blocking)
Pre-existing Mac home-dir live-DB path in committed N3 evidence (`nas-copied-db-n3/…/02-live-db-source-proof.md:3`).
Low-sensitivity, already committed. Redact only under explicit evidence-maintenance authorization (§6); do not rewrite
history otherwise.
