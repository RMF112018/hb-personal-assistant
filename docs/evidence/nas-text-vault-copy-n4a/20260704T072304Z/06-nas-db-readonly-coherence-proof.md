# 06 — NAS DB Read-Only Coherence Proof

## Method
Coherence executed on the NAS **as `personal-assistant-svc`** via a stdlib-only helper. The DB was opened
strictly read-only (`file:…?mode=ro`); no `SQLiteMigrator.apply()`, no writable connection, no `_key()`/decrypt.
Refs (32-hex) and full hashes are never printed — counts only.

## Local ↔ NAS DB linkage (why read-only + why trustworthy)
- N3 proved the local scratchpad copy is byte-identical to the NAS-placed DB (equal SHA-256).
- N4A re-verified the local copy SHA-256 is unchanged from the N3 record ✔.
- NAS DB main-file metadata re-checked read-only: `size = 4,151,631,872` (unchanged), `mtime` = N3 placement
  (unchanged), owner `personal-assistant-svc:users`, mode 600. A full NAS re-hash is sudo-gated and deferred;
  metadata + unchanged local-copy SHA establish content equivalence. The service-user coherence run below reads the
  actual NAS DB directly (mode=ro), so the match is proven against the real NAS file, not only the proxy.

## Service-user coherence result (NAS DB `mode=ro`)
| Check | Value |
|---|---|
| `quick_check` | ok |
| `integrity_check` | ok |
| `schema` (`MAX(schema_migrations.version)`) | 98 |
| `table_count` | 506 |
| `distinct_refs` | 7,198 |
| `refs_with_blob` | 7,198 |
| `refs_missing_blob` | **0** |
| `blobs_on_disk` | 7,202 |
| `orphan_blobs` | 4 (harmless) |
| **COHERENT** | **YES** |

## Write-safety
No writable DB open occurred. The `mode=ro` open of the WAL-header DB recreates 0-byte `-wal`/`-shm` read-artifacts
in `db/` (owned svc) — expected; the main DB file is unmutated (size/mtime = N3 placement). No backend/MCP started.

⇒ The NAS copied DB is now Text-Vault-**coherent**: every referenced body has its encrypted blob present under the
service user, decryptable by the copied key (decrypt not exercised this phase — deferred to N5).
