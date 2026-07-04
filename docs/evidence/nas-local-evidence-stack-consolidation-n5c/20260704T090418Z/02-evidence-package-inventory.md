# 02 — Evidence Package Inventory

All six NAS-migration evidence packages inventoried. Committable = files outside `local-sensitive/`.

| Package | Exists | Committable files | local-sensitive | Closeout | Ext (committable) | Disallowed artifacts | Large >256K |
|---|---|---|---|---|---|---|---|
| `nas-copied-db-n3/20260704T060648Z` | yes | 11 | 4 | yes | md | 0 | 0 |
| `nas-secrets-auth-text-vault-n4/20260704T065942Z` | yes | 12 | 1 | yes | md | 0 | 0 |
| `nas-text-vault-copy-n4a/20260704T072304Z` | yes | 11 | 1 | yes | md | 0 | 0 |
| `nas-vault-source-roots-n5/20260704T074519Z` | yes | 15 | 1 | yes | md | 0 | 0 |
| `nas-vault-mirror-config-draft-n5a/20260704T080459Z` | yes | 15 | 1 | yes | 13 md + 1 json + 1 yml | 0 | 0 |
| `nas-scratch-dryrun-availability-n5b/20260704T082556Z` | yes | 16 | 2 | yes | 14 md + 1 json + 1 yml | 0 | 0 |

## Notes
- The `.json`/`.yml` files in N5A/N5B are the **non-activated config drafts** (allowed evidence) — not runtime configs.
- `local-sensitive/` file counts are the git-ignored operator detail (host/paths/probe-detail); none tracked.
- **Disallowed-artifact scan (committable):** zero `.sqlite`, `.sqlite-wal`, `.sqlite-shm`, `.enc`, `.key`, `.tar`,
  `.zip`, `token*`, `.bin`, `.pem` in any of the six packages (confirmed via `git ls-files` on the NAS-6 paths).
- No suspicious large files (all committable files < 256 KB).

## Tracked-file safety (git ls-files)
- Every tracked file under the six NAS packages is `.md`, `.json`, or `.yml`.
- Zero `local-sensitive/` files are tracked across the six packages.
- (A repo-wide `git ls-files` shows `.zip`/`token`-named files under **unrelated** historical evidence packages —
  construction-intelligence / forecast / procore / schedule — which are **out of scope** for this NAS stack and
  predate it. None are in the six NAS packages.)
