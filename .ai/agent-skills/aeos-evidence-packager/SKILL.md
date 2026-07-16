---
name: aeos-evidence-packager
description: Create an immutable, machine-indexed AEOS evidence bundle from commands, tests, diffs, metrics, and repository state while preserving failed attempts and separating evidence from narrative.
---


## Governing contract

Read and apply `../_aeos-shared/AEOS_SKILL_OPERATING_CONTRACT.md` before using this skill. Repository governance remains authoritative.

Do not use this skill when the active goal state or operator authorization does not permit its workflow.

# AEOS Evidence Packager

## Use when

Use whenever a planning, implementation, audit, corrective, migration, benchmark, or readiness claim requires durable evidence.

This skill packages evidence; it does not decide whether the evidence is sufficient for approval.

## Evidence bundle convention

Use an approved goal-specific location. Recommended:

```text
docs/evidence/<goal-or-phase>/<checkpoint-or-work-item>/<run-id>/
```

or, when the goal explicitly keeps pre-merge artifacts under `.ai/`:

```text
.ai/aeos/goals/<goal-id>/evidence/<checkpoint-or-work-item>/<run-id>/
```

Do not invent a new canonical location when the repository already defines one.

## Required contents

As applicable:

```text
00-summary.md
artifact-manifest.json
evidence-index.json
repository-state.json
commands.log
stdout/
stderr/
test-results/
metrics/
diff.patch
environment.json
limitations.md
```

## Procedure

### 1. Create an immutable run identity

Use a timestamp or deterministic run identifier. Never overwrite a prior failed or invalid run.

### 2. Capture repository identity

Record:

- repository path;
- branch;
- upstream;
- base SHA;
- current SHA;
- dirty state;
- diff summary.

### 3. Capture execution receipts

For each command, record:

- sequence number;
- exact command;
- working directory;
- start/end timestamps;
- exit code;
- stdout path;
- stderr path;
- timeout or interruption status.

Avoid logging secrets or sensitive payloads.

### 4. Capture structured results

Prefer native machine output:

- JUnit XML;
- JSON benchmark results;
- database-check output;
- schema inventory;
- migration receipts;
- metrics files;
- checksums.

Do not convert all evidence into prose.

### 5. Build the evidence index

Each item must have:

```json
{
  "evidence_id": "EVID-001",
  "path": "relative/path",
  "kind": "test_result",
  "sha256": "...",
  "claim_ids": ["CLAIM-001"],
  "generated_by": "command or tool",
  "status": "complete"
}
```

### 6. Redact and validate

Check for:

- tokens;
- credentials;
- private keys;
- full email bodies or prohibited source content;
- absolute paths when prohibited by the artifact contract;
- unstable temporary paths;
- malformed or missing files.

Record redactions. Do not silently alter source evidence without retaining a sanitized-generation receipt.

### 7. Preserve evidence classes

Label:

- direct;
- derived;
- narrative;
- external;
- unavailable.

Agent-authored summaries are narrative evidence.

### 8. Write summary and limitations

The summary must cite evidence identifiers. The limitations file must disclose missing, invalid, or nonrepresentative evidence.

### 9. Validate hashes and schema

Validate the evidence index against the shared schema where practical. Recompute artifact hashes after final write.

## Prohibitions

Do not:

- delete failed runs;
- replace raw outputs with only a summary;
- claim tests ran when only commands were proposed;
- cite a file that does not exist;
- package secrets;
- classify evidence sufficiency beyond the authorized workflow.
