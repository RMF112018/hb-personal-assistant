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
