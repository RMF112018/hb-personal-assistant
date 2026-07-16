# PUBLIC_REDACTION_POLICY — sanitized public tier (NO raw values)

- classification: Audits (supporting evidence)
- version: 1.0 · created_utc: 2026-07-16
- This is the **public** counterpart to the private raw-value map. It states categories, placeholder conventions,
  and preservation rules. It contains **no** raw sensitive values. The raw→placeholder map lives only in the
  private evidence store.

## Why sanitization
The GitHub repository is PUBLIC. AEOS 04 §11 requires redaction of secrets, PII, **and sensitive operational
details**. The original package disclosed production topology; this public tier removes it while preserving every
V124→V127 readiness claim in verifiable form.

## Sensitivity categories → placeholder conventions
| Category | Examples of what is removed | Placeholder form |
|---|---|---|
| A — NAS host / SSH access | external edge-endpoint FQDN, device hostname, SSH alias/port, private-key filename, edge provider | `<mcp-endpoint>`, `<nas-hostname>`, `<nas-host>`, `<ssh-port>`, `<ssh-key-file>`, `<edge-provider>` |
| B — Host filesystem paths | NAS volume/app-support paths, home directories | `<managed-root>`, `<nas-vol2>`, `<user-home>`, `<user-home-nas>` |
| C — Internal network / ports | internal Docker network name/addresses, MCP port | `<internal-net-name>`, `<internal-addr-N>`, `<mcp-port>` |
| D — DB / device identity | device/inode numbers, live DB byte size | `dev=<dev>`, `ino=<ino>`, `<db-size-bytes>` |
| E — Image / deployment identity | deployed image id + deployed source revision; candidate image digests | `<deployed-image-id>`, `<deployed-revision>`, `<candidate-*-digest>` |
| F — Unrelated host inventory | third-party / dev containers + images + digests unrelated to this project | removed with a count-only note |

## Preservation rules (what is KEPT)
- Public git SHAs of this repo (e.g. `97efbb6b`, the evidence subject) — inherently public.
- Schema version numbers (V124..V127), AEOS/finding IDs, acceptance-criteria IDs, generic app port 8000.
- Every claim, status, and finding — with enough structure to verify it — is preserved; only the sensitive
  identifiers behind the claim are replaced with stable placeholders.

## Removed-content categories (kept private, referenced by SHA-256)
- Full `docker images` / `docker ps` inventory and all image/layer digests.
- Running-container inspect JSON, deployed-image inspect JSON, OAuth request/response logs.
- Verbose build log, NAS image-load log, full candidate-image inspect JSON.
- Command receipts with raw host/target; the operator authorization record; the Docker image archive.

## Publication-review method
A two-stage fail-closed gate (Gate A precommit, Gate B postcommit) inspects filenames, all text/binary content,
manifests, archive members, the git diff, commit message, and every raw private-map token, plus generic
sensitive-value patterns. Any unresolved match fails closed. This policy plus `19b_PUBLICATION_SENSITIVITY_REVIEW.md`
records the outcome. An independent publication review remains REQUIRED before any push.
