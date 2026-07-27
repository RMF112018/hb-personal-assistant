---
name: aeos-evidence-packager
description: Create an immutable machine-indexed AEOS evidence bundle bound to exact repository and environment identity, preserving failed attempts and recording representation, hash scope, provenance, and limitations without deciding approval.
---

## Governing contract

Read and apply `../_aeos-shared/AEOS_SKILL_OPERATING_CONTRACT.md`. Repository
governance remains authoritative.

# AEOS Evidence Packager

## Use when

Use whenever a planning, implementation, audit, corrective, migration,
benchmark, readiness, post-merge, or cleanup claim requires durable evidence.
This skill packages evidence; it does not decide sufficiency or authorize action.

## Location

Use the approved repository or goal-specific evidence location. Do not invent a
new canonical root when one already exists. Every run receives an immutable run
identity; never overwrite a failed or invalid run.

## Required bundle contents

As applicable:

```text
00-summary.md
artifact-manifest.json
evidence-index.json
repository-state.json
environment.json
commands.log
stdout/
stderr/
test-results/
metrics/
diff.patch
limitations.md
redaction-receipt.md
```

## Procedure

### 1. Capture exact identity

Record repository path, authenticated remote, default branch, registered branch
and worktree, upstream, base SHA, exact head SHA, PR/checks, dirty state, diff
summary, goal, work item, checkpoint, and authorization.

For post-merge evidence, also record the accepted target-branch commit and its
relationship to the reviewed candidate.

### 2. Capture command receipts

For each command record sequence, exact command, working directory, start/end
timestamps, exit code, stdout/stderr paths, timeout/interruption status, and
environment. Avoid secrets.

### 3. Preserve native machine output

Prefer JUnit XML, JSON, database output, migration receipts, schemas, metrics,
CI results, and raw logs. Preserve failed and invalid attempts. Do not reduce all
evidence to prose.

### 4. Build a representation-aware evidence index

Each item includes:

```json
{
  "evidence_id": "EVID-001",
  "path": "relative/path-or-stable-object-id",
  "kind": "test_result",
  "representation": "raw_file",
  "mime_type": "text/plain",
  "hash_scope": "stored_raw_bytes",
  "sha256": "...",
  "source_relation": "direct",
  "claim_ids": ["CLAIM-001"],
  "generated_by": "command or tool",
  "repository_head": "...",
  "environment": "...",
  "verification": "computed_sha256",
  "status": "complete"
}
```

Valid hash scopes are `stored_raw_bytes`, `source_bytes`, `exported_bytes`, and
`not_applicable`. Hashes from different representations are not interchangeable.
Native Google Docs use stable Drive identity and `hash_scope: not_applicable`
unless a separately identified source/export is hashed.

### 5. Classify evidence

Label evidence as direct, derived, narrative, external, unavailable, or
not-applicable. Agent summaries are narrative evidence.

### 6. Redact and validate

Check for secrets, credentials, private keys, prohibited personal/source
content, unstable paths, malformed files, and unsupported identity claims.
Record redactions and derivative provenance; do not silently alter evidence.

### 7. Write summary and limitations

The summary cites evidence IDs. Limitations disclose missing, stale, invalid,
nonrepresentative, inaccessible, or representation-ambiguous evidence.

### 8. Validate schema and hashes

Validate the evidence index against the shared schema. Recompute applicable
hashes after final write and confirm all referenced paths or stable object IDs
exist.

## Prohibitions

Do not delete failed runs, replace raw outputs with only summaries, claim tests
ran when only proposed, cite nonexistent evidence, package secrets, imply
cross-representation byte identity, or decide approval/readiness outside the
authorized workflow.
