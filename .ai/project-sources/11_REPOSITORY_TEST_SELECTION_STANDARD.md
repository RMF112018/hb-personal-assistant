---
standard: AEOS
version: "1.2"
status: normative
license: internal-use
---

# 11 — Repository Test Selection and Failure Disposition Standard

## 1. Purpose

This standard defines proportional, evidence-oriented test selection and durable
disposition of every observed test failure for
`RMF112018/hb-personal-assistant`. It prevents both under-testing and repeated
execution of expensive suites that add no material assurance to the active
change.

It does not weaken acceptance criteria, safeguards, or merge/release gates. It
separates edit ownership from the requirement that the integrated candidate
ultimately satisfy every applicable gate.

## 2. Mandatory suite mapping

Every mandatory test or validation command SHALL map to at least one of:

1. an explicit acceptance criterion;
2. changed behavior;
3. a direct or demonstrated transitive dependency;
4. a changed shared-infrastructure surface;
5. a named regression risk;
6. an exact merge, release, deployment, or production-readiness gate.

A suite SHALL NOT become mandatory solely because an earlier work item ran it, a
generic template lists it, or an agent has historically run it. A mapped test in
an approved authorization remains binding unless an exact higher-authority or
later operator decision supersedes it. Conflicts follow Standard 07 §7 and fail
closed to a deviation report.

## 3. Execution stages

### 3.1 Inner loop

After a small edit, run the smallest test that can falsify the current claim: a
failing node ID, one class or file, or a narrow changed-module syntax, lint,
type, or import check. Do not run broad domain bundles, unrelated canaries, or
the merge-safe suite after every edit or conversational turn.

### 3.2 Coherent slice

After a coherent implementation slice, run directly affected tests, direct
caller/consumer seams, changed-file static checks, and required adversarial or
invariant tests.

### 3.3 Candidate validation

Before creating or updating a review candidate, run the complete bounded
work-item acceptance suite defined by the approved plan or authorization, as
modified only by a later exact decision.

### 3.4 Committed-SHA checkpoint

At the final committed SHA, capture the work-item suite, static checks, baseline
comparison, triggered canaries, command, environment, dependency/configuration
identity, result, and evidence hash. A costly suite normally runs once per
materially different candidate SHA, not once per agent turn.

### 3.5 Merge and release validation

The canonical merge-safe repository gate is:

```bash
bash scripts/test-safe.sh
```

It runs the full safe Python scope `tests/` with markers `integration`, `manual`,
and `live` excluded, followed by the frontend Vitest suite. It fails if required
frontend dependencies are unavailable. `bash scripts/test-safe.sh --collect-only`
validates Python collection and intentionally does not claim frontend execution.
`--python-only` and `--frontend-only` are diagnostic component runs and do not
individually satisfy the full gate.

Unfiltered `pytest` is permitted only under an exact authorization that accepts
the external/manual/live effects and required environment. Selected targets,
marker overrides, or arbitrary pytest arguments are prohibited through the
canonical script because they would no longer represent the merge-safe suite.

Run the full safe gate for merge or release readiness, broad cross-domain
refactors, global fixtures or discovery, dependency or packaging changes,
runtime bootstrap, or behavior reasonably capable of affecting unrelated
areas. Focused acceptance evidence does not replace an applicable merge gate,
and a full gate does not replace focused acceptance evidence.

Merge readiness requires zero unresolved failures in every applicable required
suite.

## 4. Impact classes

| Class | Typical surface | Validation |
|---|---|---|
| Local | One isolated function, module, or policy | Targeted tests and changed-file checks |
| Domain | Multiple files in one bounded domain | Domain suite and direct integration seams |
| Shared infrastructure | Migrator, schema/bootstrap, common DB, packaging, global fixtures | Affected domains and demonstrated canaries |
| Cross-domain | Shared API, CLI, contract, or refactor | All affected domains and broader selected regression tests |
| Merge/release | Integrated candidate | `bash scripts/test-safe.sh` plus gate-specific evidence |

## 5. Forecasting and schedule bundles

Run `scripts/test-forecasting.sh` for forecast generation, configuration, read
models, semantic/readiness gates, forecast API/UI, forecast-related financial
normalization, or demonstrated shared dependencies.

Run `scripts/test-schedule.sh` for schedule ingestion, XER/XML/MSP parsing,
quality, CPM/critical path, mapping, projection, migration, or demonstrated
shared dependencies.

The schedule bundle is a cross-domain canary for
`src/hb_assistant/store/migrator.py`, shared schema/bootstrap behavior, or other
verified common database infrastructure. It is not a default canary for isolated
source-index repository, connector, model, or service changes. Run both bundles
only when both domains or shared infrastructure used by both are affected.

## 6. Failure classification

Every failing test SHALL be preserved and classified:

| Classification | Required disposition |
|---|---|
| Candidate regression | Stop the affected checkpoint and correct within the active work item |
| Reproducible pre-existing product defect | Preserve base/candidate evidence and request separate corrective authorization |
| Invalid or stale test | Request bounded test-correction work; do not weaken, delete, or skip without evidence and review |
| Flaky or nondeterministic test | Preserve repeated-run evidence and request stabilization work |
| Environment or configuration failure | Correct or formally document the environment; do not report product green |
| Relationship unknown | Treat as potentially related and stop the affected checkpoint |

A failure is not unrelated because its filename or domain differs. Pre-existing
status requires reproduction on the immutable base SHA under a materially
equivalent command, dependencies, environment, fixtures, and inputs, or
equivalent direct causal evidence.

## 7. Durable failure identity and ownership

Every observed failure SHALL immediately receive a durable record under
`docs/governance/test-failure-triage.md`. The preferred GitHub issue template is
`.github/ISSUE_TEMPLATE/test-failure.yml`, with stable identity
`TF-<issue-number>`.

The record must contain discovery time and source work item, exact failing IDs,
triage owner, classification state, base/candidate evidence, affected criterion
or gate, disposition, authorization state, corrective identity when authorized,
independent review, integrated-candidate result, and closure evidence.

The initial classification is `RELATIONSHIP_UNKNOWN` unless direct evidence
supports another state. Corrective authorization starts as
`AWAITING_AUTHORIZATION` unless an exact authorization already exists. A known
failure may remain outside the primary work item's edit scope, but it may not be
unowned, untracked, or treated as green.

## 8. Parallel corrective work

A separate corrective agent MAY work in parallel only when all are true:

1. base-SHA reproduction proves the failure pre-existing;
2. current acceptance evidence remains valid;
3. the corrective file/test surface is bounded;
4. edit and evidence ownership do not overlap;
5. no shared schema, migrator/bootstrap, global fixture, discovery,
   dependency/configuration, security control, or common surface is involved;
6. a separate branch and, when local, worktree are registered;
7. a separate explicit authorization, evidence package, and independent review
   exist;
8. integration is separately authorized;
9. the combined candidate reruns every applicable checkpoint and merge gate.

The primary agent may create the triage record and request authorization, but
shall not create or activate the corrective agent on its own authority. Unknown
or overlapping relationships block the affected checkpoint.

## 9. No-known-failure integration rule

Focused implementation may continue only within the controls above. No
integrated candidate is merge-ready while an applicable required test has an
unexplained or unresolved failure. This requires zero unexplained failures,
zero untracked pre-existing failures, zero required-gate failures, and zero
waivers based only on age or apparent domain distance.

## 10. Evidence reuse

Evidence MAY be reused only when the tested SHA, command/targets,
dependency/configuration identity, interpreter/material environment, fixtures or
external inputs, and evidence purpose are unchanged and recorded. Do not rerun
an identical suite for a bookkeeping-only turn. Rerun when any identity changes
in a way capable of affecting the result. Declare parent-baseline reuse in the
evidence manifest.

## 11. Plan and authorization requirements

Plans and authorizations SHALL distinguish inner-loop tests, candidate tests,
committed-checkpoint tests, conditional canaries with triggers, merge/release
tests, failure-classification evidence, durable failure ownership, parallel work
when authorized, and final integrated-green requirements. Each required suite
shall include its criterion, dependency, risk, or gate mapping.

Approved historical plans are not silently rewritten. Use a superseding plan or
an exact operator decision.

## 12. Stop conditions

Stop and report when plan and standard conflict without a superseding decision,
blast-radius evidence is unavailable for high-risk change, a required suite
cannot execute, narrowing would weaken a criterion or safeguard, a failure is
not proven pre-existing, parallel work overlaps, or the combined candidate
remains red.

## 13. Reporting

Reports SHALL state tests and exact results, selection mappings, required tests
not run, every failure identity/classification and evidence, triage and
corrective identities, reused evidence, deferred broader gates, integrated-green
status, and residual unverified areas.
