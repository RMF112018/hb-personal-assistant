# Cleanup ledger

| Artifact | Disposition |
|----------|-------------|
| pytest temp DBs under /tmp/pytest-* | Auto-removed by pytest |
| Generated output tests (n8c24 + hardening archive test) | Wrote under tmp_path outputs only; not production |
| Live production NAS data | **Not mutated** |
| Evidence under docs/evidence/nas-source-index-client-performance-hardening/ | Intentionally retained |

| Closeout evidence `05-*` files | Intentionally retained in repo evidence pack |
| Live hosted NAS mutations | None (401 without origin auth; no writes attempted) |
| Local FastMCP temp DBs for discovery | Created under /tmp and discarded |

## 09 post-deploy live matrix

- `OUTPUT-20260709-004` (postdeploy-matrix-temp-md): archived_in_case_9
- `OUTPUT-20260709-005` (postdeploy-matrix-temp-zip): archived_in_case_9
- Bearer token: not written to evidence

## 10 alias dispatch proof

- Pre-redeploy: no temp outputs (assistant_output_stage tool_not_registered)
- Staged image `/tmp/hb-nas-alias-fix-fa266c529375.tar.gz` — remove after load
- Bearer token not written to evidence

## 10 alias dispatch post-redeploy

- `OUTPUT-20260709-006` (alias-postdeploy-temp-md): archived
- `OUTPUT-20260709-007` (alias-postdeploy-temp-zip): archived
- Bearer token not written to evidence

