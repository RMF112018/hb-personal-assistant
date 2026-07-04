# 06 — Vault Mirror Equivalence Proof

Structural equivalence between the live source vault and the NAS mirror.

| Metric | Source (Mac) | NAS mirror | Equivalent |
|---|---|---|---|
| Files (excl `.DS_Store`) | 221 | 221 (`nas_file_count`) | ✅ |
| Markdown notes | 155 | 155 (`nas_md_count`) | ✅ |
| Directories | 63 | 63 (tar: 284 entries − 221 files) | ✅ |
| Symlinks | 0 | 0 (none in tar) | ✅ |
| `.DS_Store` | 9 (source) | 0 (deliberately excluded) | ✅ (by design) |
| Total size | 4,446,272 B | equivalent (gnutar sha-matched on transfer) | ✅ |

## Equivalence argument
1. **Content equivalence via sha-matched transfer.** The local gnutar of the exact source set was sha256-verified
   byte-for-byte identical after streaming to the NAS (sha_match=YES). Extraction is lossless, so the NAS tree's file
   contents equal the source tree's (minus the intentionally-excluded `.DS_Store` noise).
2. **Count equivalence post-extract.** Independent post-extract enumeration on the NAS gives `nas_file_count=221` and
   `nas_md_count=155`, matching the source's 221 / 155.
3. **Structure equivalence.** The tar preserves the relative directory tree (284 entries = 221 files + 63 dirs);
   because vault addressing is a single relative root, the relative tree is what identity and links depend on — and it
   is preserved exactly.

## Reachability / read proof (service user)
`svc_can_stat_dir=yes` and `svc_md_count=155` — the demoted `personal-assistant-svc` can traverse the mirror and
enumerate all notes. This is a filesystem reachability proof, **not** an ingestion or availability-probe run (no
`obsidian_source_root_availability_probe.py` executed — the NAS path is not locally mounted; that stat-only probe is
deferred to N5B where it runs on-NAS).

## Conclusion
The NAS mirror is a structurally-equivalent, service-readable copy of the source vault. Divergence is limited to the
deliberately-omitted `.DS_Store` metadata. Equivalence: **PASS**.
