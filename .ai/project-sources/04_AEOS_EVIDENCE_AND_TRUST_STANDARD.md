---
standard: AEOS
version: "1.1"
status: normative
license: internal-use
---

# 04 — AEOS Evidence and Trust Standard

## 1. Purpose

This standard defines admissible evidence, provenance, exact-identity binding,
representation scope, trust states, insufficiency, and fail-closed behavior.

## 2. Evidence Principles

Evidence SHALL be:

- **specific** — identify exactly what was observed;
- **reproducible** — include commands, inputs, environment, and outputs;
- **relevant** — support only the claim actually verified;
- **provenanced** — identify repository, runtime, CI, tool, or human source;
- **current** — be fresh enough for the decision;
- **identity-bound** — identify the exact artifact, SHA, environment, or runtime
  observation;
- **representation-aware** — identify which bytes or native object are
  authenticated.

Agent narrative and prior conversations are claim indexes, not proof.

## 3. Evidence Authority

For deployed behavior, authenticated runtime evidence has priority. For
engineering identity and lifecycle, authenticated repository and GitHub state
has priority. Approved specifications and governance define expected behavior
but do not prove implementation or runtime results.

Publication systems are authoritative for their own object identity and
publication history, not for repository execution state.

## 4. Exact Repository Identity

Material repository evidence SHALL record, as applicable:

- repository and authenticated remote;
- default and target branch;
- worktree identity and path;
- base SHA, exact head SHA, and merge base;
- pull request and required checks;
- dirty/untracked state;
- reviewed or tested head;
- accepted merge identity.

Evidence from one head SHALL NOT be presented as current-head evidence after a
later commit without re-verification.

## 5. Representation and Hash Scope

Each material evidence item SHOULD record:

```yaml
representation:
mime_type:
hash_scope:
sha256:
source_relation:
verification:
```

Valid hash scopes:

- `stored_raw_bytes`
- `source_bytes`
- `exported_bytes`
- `not_applicable`

A hash authenticates only the identified representation. Cross-representation
hash equivalence SHALL NOT be inferred.

A native Google Doc has stable Drive identity and revision history but no
portable raw-byte SHA-256. Its publication identity may be verified, while
source-byte or export-byte claims require separately identified evidence.

## 6. Evidence Strength

### Strong evidence

- authenticated repository state and diffs;
- exact commit SHAs;
- full command output and exit codes;
- named tests with complete results;
- CI checks bound to exact head;
- runtime logs and API responses;
- database validation;
- migration and deployment receipts;
- monitoring data;
- representation-scoped hashes.

### Moderate evidence

- structured implementation reports;
- summarized output with command and context;
- static analysis;
- partial logs or screenshots with limitations.

### Weak evidence

- agent claims;
- uncited summaries;
- "tests passed" without identity or output;
- compilation alone;
- mock-only proof for integration-critical behavior;
- publication receipt offered as technical correctness evidence.

Weak evidence SHALL NOT support high-consequence conclusions alone.

## 7. Required Evidence by Claim

### Implemented

Requires diff, changed files, exact head, implementation summary, and acceptance
traceability.

### Tested

Requires exact command, suite or node IDs, complete results, exact head, and
environment.

### Regression-safe

Requires proportional test selection, changed-surface analysis, failure
classification, and applicable required-safe suites.

### Migration-safe

Requires migration identity, forward evidence, recovery strategy, data
integrity checks, and compatibility analysis.

### Reviewed or approved

Requires review identity, independent context, exact reviewed artifact and head,
evidence basis, disposition, and stale-on-head-change rule.

### Merged

Requires authenticated accepted target-branch identity. It does not prove
cleanup, deployment, or production readiness.

### Closed

Requires post-merge validation or explicit not-required decision plus a cleanup,
retention, or blocker receipt.

### Production-ready

Requires separately scoped implementation audit, runtime validation,
observability, rollback, and risk disposition.

## 8. Evidence Package Requirements

An evidence package SHALL include:

- package and run IDs;
- goal, work item, and checkpoint;
- repository, branch, worktree, base, and exact head;
- environment identity;
- commands, timestamps, exit codes, stdout, and stderr;
- test totals and failing node IDs;
- failure classifications and baseline evidence;
- CI references;
- runtime and migration evidence when applicable;
- diff and artifact manifests;
- representation and hash scope;
- limitations and redactions;
- immutable preservation of failed and invalid attempts.

## 9. Branch and Worktree Closeout Evidence

Cleanup or pruning claims require:

- complete relevant inventory;
- no-prune remote fetch when remote state matters;
- dirty/untracked preservation;
- integration or patch-equivalence proof;
- target-specific dry-run previews;
- lock, storage, and process-use assessment;
- separate authorization for each destructive or pruning action;
- exact commands and outputs;
- cleanup, retention, or blocker receipt.

Absence of an item from a partial inventory is not proof that it does not exist.

## 10. Trust States

Assign trust to individual claims:

- `trusted`
- `partially_trusted`
- `untrusted`
- `not_evaluated`
- `conflicting`

Use claim classifications:

- `VERIFIED`
- `CLAIMED_NOT_VERIFIED`
- `ASSUMED`
- `UNKNOWN`
- `UNAVAILABLE`
- `NOT_APPLICABLE`

## 11. Fail-Closed Rules

Use `INSUFFICIENT EVIDENCE` or block the transition when:

- identity or source authority is unclear;
- evidence is stale or conflicts;
- exact test output is missing;
- the reviewed head changed;
- runtime behavior is claimed without runtime evidence;
- migration evidence is missing;
- representation scope is ambiguous;
- cleanup is proposed without inventory and preservation;
- production or risk conclusions exceed the evidence.

Failing closed does not assert a defect; it limits the conclusion.

## 12. Redaction and Sanitization

Evidence may be redacted for secrets, personal information, or sensitive
operations. Redaction SHALL preserve validation structure and record what was
redacted, why, and how the sanitized derivative relates to the source.

Never silently replace source evidence with a summary.

## 13. Evidence Anti-Patterns

Noncompliant behavior includes:

- using old CI after a new commit;
- claiming all tests passed without commands;
- hiding failures as unrelated without classification;
- using a Drive publication as repository truth;
- claiming a native document matches source bytes without proof;
- deleting failed runs;
- treating mergeability or publication as readiness;
- claiming branch cleanup from an incomplete inventory.
