# 05 — `local-sensitive/` Ignore Check

## Rule
`.gitignore:202` → `docs/evidence/**/local-sensitive/` — every `local-sensitive/` directory under any evidence
package is git-ignored.

## Verification
- `git check-ignore -v` confirms IGNORED for the `local-sensitive/` content of **all six** NAS packages:
  - `nas-copied-db-n3/…/local-sensitive/*`
  - `nas-secrets-auth-text-vault-n4/…/local-sensitive/*`
  - `nas-text-vault-copy-n4a/…/local-sensitive/*`
  - `nas-vault-source-roots-n5/…/local-sensitive/*`
  - `nas-vault-mirror-config-draft-n5a/…/local-sensitive/*`
  - `nas-scratch-dryrun-availability-n5b/…/local-sensitive/*`
- `git ls-files 'docs/evidence/nas-*/**/local-sensitive/*'` → **count = 0** tracked.

## Posture
- Raw sensitive operational files (host, absolute paths, probe path-detail, full hashes/refs) live only inside these
  ignored dirs.
- No `local-sensitive/README.md` is tracked — consistent with the established convention for this stack (leave ignored).
- This N5C package follows the same convention: its `local-sensitive/README.md` is ignored, not committed.
