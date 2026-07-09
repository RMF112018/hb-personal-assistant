# Cleanup ledger

| Artifact | Disposition |
|----------|-------------|
| pytest temp DBs under /tmp/pytest-* | Auto-removed by pytest |
| Generated output tests (n8c24 + hardening archive test) | Wrote under tmp_path outputs only; not production |
| Live production NAS data | **Not mutated** |
| Evidence under docs/evidence/nas-source-index-client-performance-hardening/ | Intentionally retained |
