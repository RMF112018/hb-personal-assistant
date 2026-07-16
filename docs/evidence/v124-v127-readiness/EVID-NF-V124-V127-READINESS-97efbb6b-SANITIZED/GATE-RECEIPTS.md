# Publication Gate Receipts (sanitized) — tool identities + method (v6)

- classification: Audits (supporting evidence)
- version: 6.0 · created_utc: 2026-07-16
- NOTE: the raw scanner (`pub_gate_v6.sh`) embeds the raw sensitive token patterns and is therefore **private**
  (publishing the pattern list would re-disclose the values). This in-package receipt records **tool identities and
  method only**. Per the v6 freeze discipline (V6-PLAN-007) it is finalized **before** the final index/register/
  MANIFEST and is a frozen committed file; it therefore asserts **no** Gate A or Gate B outcome. The actual gate
  results are recorded in the **external private Gate A and Gate B receipts** (see "Gate results" below), which the
  independent reviewer authenticates. The scanner source itself is supplied to the reviewer in
  `PRIVATE-REVIEW/scanner/`; the index/register generators in `PRIVATE-REVIEW/generators/`.

## Tool identities (static)
- Publication gate: `pub_gate_v6.sh` (private), fail-closed.
  SHA-256 `2036a50e66f35fe58b87e1879421e092fd332ba35ae8f886d8f44a98bf44f1ec`.
- Index generator: `gen_index.py` SHA-256 `00424beb1e80187eb7e1367cc7bc7c5a33168b4aaa122eece77dcd5915da460c`
  (version label parameterized — never hardcoded — and the exact-file register is enumerated in the index). This is
  the **actual final generator** that produced the committed `20_EVIDENCE_INDEX.md`; it matches the
  `PRIVATE-REVIEW/generators/gen_index.py.sha256` sidecar shipped to the reviewer (V5-CORR-AUD-002 corrected;
  the prior private stale-hash workaround is removed).
- Exact-file register generator: `gen_register.py` SHA-256
  `eb9073e0613df5862950c291fdb357eb53125910770e4192f38f5c990031d524`.

## Method (categories only — not the raw patterns)
- `grep -rnIE` per token category over the whole package tree; plus **generic structural categories** (fail-closed):
  dev/ino/mtime/ctime numeric fields, `mode=0o…`, permission rows, backup/bench filename patterns, UID/GID columns,
  raw container mount paths, software/kernel version strings + local host architecture, rollback tags, compact
  timestamps, comma-grouped byte counts, and bare decimal integers ≥7 digits not embedded in hex; plus a bare-long-hex
  sweep (`[0-9a-f]{16,}`) excluding hash-list files, whitelisted public git SHAs, and the bounded-summary
  `Private evidence-artifact SHA-256` field.
- **v5 disclosure classes (fail-closed):** ISO datetime tokens; runtime-duration/age language; internal-binding and
  edge-endpoint literals; port/protocol tokens; local toolchain-path markers; high-count row references;
  environment-variable-name tokens; and workspace/template naming.
- **v6 disclosure class added (fail-closed, V5-CORR-AUD-001 / V6-PLAN-008):** a **case-insensitive**, **portable
  POSIX-class** bare workspace-store naming rule (singular + plural), applied via the `scani()` helper. It is
  fixture-proven (the scanner fixture receipt shipped in `PRIVATE-REVIEW/scanner/`): matches the singular/plural
  forms including capitalized and parenthesized variants; rejects the `-ed`/`-ing`/`default` decoys; detects all
  reviewed prior occurrences; returns 0 on this tree.
- Per-summary checks (all 8 bounded summaries): BOUNDED-PUBLIC-SUMMARY marker; the three-field trust schema
  (Summary artifact trust / Underlying execution evidence trust / Trust does not transfer); a private artifact ID + a
  64-hex private SHA; exactly one normalized `Observation time` (`YYYY-MM-DD UTC`); and no other date/time token.
- Verbatim-line diff: each bounded summary is diffed against its private raw counterpart; any substantive line
  (len>20, non-label) copied verbatim fails closed.

## Gate method (results are external — this file asserts none)
- **Gate A — precommit, no-write.** Run against the **frozen** candidate tree (after the final index/register/MANIFEST
  are generated; no write to any public file). Steps: (1) filenames; (2) all text/binary content; (3) manifest +
  register + sidecar; (4) archive member names; (5) fresh reconstruction extract; (6) every raw private-map token;
  (7) generic structural + v5 disclosure classes + the v6 workspace-store naming class; (8) per-summary checks; (9) verbatim-line
  diff vs private raw; (10) proposed commit message. Result recorded in the **external private Gate A receipt**.
- **Gate B — postcommit, no-write.** Run against the **committed** blobs. Steps: (1) `git diff <base>..HEAD`;
  (2) committed filenames + modes; (3) commit message; (4) committed blob content re-scanned; (5) reconstruction from
  the git tree vs committed MANIFEST + authentication chain; (6) absence of private artifacts and the archival ref in
  branch history; (7) exactly one commit above base. Result recorded in the **external private Gate B receipt** (this
  in-package file cannot contain its own commit SHA and, being frozen pre-commit, cannot assert a postcommit outcome).

## Gate results (external, private review tier)
- Private Gate A receipt: `PRIVATE-REVIEW/GATE-A-RECEIPT-V6.md` (frozen-tree scan result + false-positive dispositions).
- Private Gate B receipt: `PRIVATE-REVIEW/GATE-B-RECEIPT.md` (base SHA, committed SHA, diff scan, filenames/modes,
  reconstruction, commit count, governed archive `.tar.gz` SHA-256 + sidecar + reconstruction identities).

## v6 corrective note
This round (V5-CORR-AUD-001/002) generalized the residual bare workspace-store naming (singular/plural) in the public
report set to location-free terms (governance authenticated by artifact ID + SHA-256); added the portable,
fixture-tested workspace-store naming gate category; corrected the `gen_index.py` tool identity above to the actual final
generator and removed the prior private stale-hash workaround; and rebuilt the packages, index, register, manifests,
and governed review bundle as one coherent v6 set bound to a single local commit. The v4 branch-deletion process
finding (GOV-GIT-001) remains OPEN; the discarded v4 sibling commit is preserved via a durable local archival ref
(not pushed) and is intentionally **absent** from this branch's history (verified by Gate B step 6).

## False-positive dispositions (not disclosures)
- Public git SHAs of this repo (`97efbb6b` [subject], `51ce5f28`, `e247ad08`, `89c745d2`, `608e6933`, `4a5adc19`,
  `e0f3650b`, `3779bcca` [preserved-sibling ref], `9f730e68`) — inherently public (a public GitHub repo).
- Governance blob SHAs in `01`/`05` and the review-v1.2 SHA in `04` — git blob / authentication hashes of PUBLIC
  governance content.
- Self-hashes in `MANIFEST.sha256`, `EXACT_FILE_REGISTER.md`, and `20_EVIDENCE_INDEX.md`, and the private hash-index
  in `PRIVATE_EVIDENCE_REFERENCES.md` — authentication-chain hashes (public self-hashes + private-artifact hashes).
- Bounded-summary `Private evidence-artifact SHA-256` values — hashes that authenticate the private evidence
  *artifact* (not DB/backup content); allowed by REM-PLAN-013.
- Normalized `Observation time: 2026-07-16 UTC` — the evidence-collection date (REM-PLAN-018 exception).
- Platform `linux/amd64` — the candidate image target architecture, material to AC-08 image identity (the local host
  architecture string is NOT present; it is fail-closed).
- Tool identity SHAs above (`pub_gate_v6.sh`, `gen_index.py`, `gen_register.py`) — generator/scanner provenance
  hashes; this file is a hash-list member.

## Authority
`Independent publication review: REQUIRED` before any push. This receipt records tool identities + method only; it
asserts no gate outcome and does not itself authorize publication.
