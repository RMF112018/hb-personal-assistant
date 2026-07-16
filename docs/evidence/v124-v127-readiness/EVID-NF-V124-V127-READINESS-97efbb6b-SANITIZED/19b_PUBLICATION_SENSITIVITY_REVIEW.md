# 19b — Publication Sensitivity Review (AEOS 04 §11) — supplements 19

- classification: Audits (supporting evidence)
- version: 6.0 · created_utc: 2026-07-16 · tier: v6
- Present in both tiers. In the public tier it carries no raw values.

## Why this exists (EVID-AUD-001)
`19_REDACTION_AND_SECRET_SCAN.txt` was **secrets-only** (0 secrets found) and under-scoped: AEOS 04 §11 also
requires redacting **sensitive operational details**. Because the repository is PUBLIC, this review adds the §11
operational-sensitivity pass that `19` lacked.

## What was redacted for the public tier (categories, per PUBLIC_REDACTION_POLICY.md)
- A: NAS host / SSH access (external edge-endpoint FQDN, hostname, alias, port, key filename, edge provider).
- B: host filesystem paths (NAS volumes, app-support, home directories).
- C: internal Docker network name + addresses, MCP port.
- D: live DB device/inode + byte size.
- E: deployed image id + deployed source revision; candidate image digests → opaque refs.
- F: the entire unrelated host Docker inventory (≈13 unrelated services/images + digests) — removed with a
  count-only note.

## Files dropped from public (retained private, referenced by SHA-256)
`runtime/container-inspect.json`, `runtime/running-container-logs-tail.txt` (OAuth), `runtime/running-image-inspect.json`,
`image/build-amd64.log`, `image/nas-image-load.log`, `image/candidate-image-inspect.json`. Replaced by sanitized
summaries `runtime/DEPLOYED_RUNTIME_SUMMARY.md` and `image/CANDIDATE_IMAGE_SUMMARY.md`; `08` rewritten sanitized.

## What was preserved
Public git SHAs (subject `97efbb6b`), schema versions, AEOS/finding/AC IDs, generic app port 8000, and every
claim/status/finding with enough structure to verify it.

## Gate outcome (see GATE-RECEIPTS.md for the full receipt)
The hardened two-stage fail-closed publication gate ran over the whole tree, extracted archive, member names,
MANIFEST, in-worktree package, and staged/committed diff (28 categories + bare-long-hex sweep).
`Implementation-agent publication scan: PASS (Gate A: 0 unresolved matches; Gate B: recorded in GATE-RECEIPTS.md
+ the external packaging receipt)`. `Independent publication review: REQUIRED` before any push. This review does
not itself authorize publication.

## Corrective-review lineage (history — not a current-state label)
- v3 round (CORR-AUD-001): fixed prefix-only redaction that left digest/commit **suffixes**, plus operational tokens
  (row counts, DB byte size, device/inode literals, backup inventory, sudo scope, docker/kernel versions, mount
  topology, disk/scratch paths). Redaction became **full-length**; the gate gained a bare-long-hex sweep and
  operational-token categories.
- v4 round (CORR-AUD-002..006): replaced raw OS/runtime captures with bounded public summaries + two-level trust;
  produced a coherent report set and a governed independent-review bundle.
- v5 round (V4-CORR-AUD-001..004): moved the residual raw rehearsal and raw runtime/governance captures to the
  private tier behind bounded summaries; hardened the gate for ISO timestamps, runtime-age language,
  internal-binding/edge-endpoint topology, port/protocol tokens, toolchain paths, environment-variable names, and
  workspace/template naming; produced one coherent v5 report set and an independently inspectable Git bundle; and
  recorded both operator authorizations (externally hashed) before their repository mutations.
- v6 round (V5-CORR-AUD-001..002): generalized the residual bare workspace-store naming (singular/plural) in the
  public report set to location-free terms (governance authenticated by artifact ID + SHA-256); replaced the gate's
  word-boundary check with a portable POSIX-class, fixture-tested rule for that naming category; corrected the public
  `GATE-RECEIPTS.md`
  `gen_index.py` provenance to the actual final generator identity and removed the prior private stale-hash workaround;
  regenerated the report set, index, register, manifests, packages, and governed review bundle as one coherent v6
  set bound to a single local commit.
