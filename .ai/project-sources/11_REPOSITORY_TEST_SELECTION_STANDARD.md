---
standard: AEOS
version: "1.1"
status: normative
license: internal-use
---

# 11 — Repository Test Selection and Failure Disposition Standard

## 1. Purpose

This standard defines proportional, evidence-oriented test selection and the
required disposition of failing tests for `RMF112018/hb-personal-assistant`.
It prevents both under-testing and repeated execution of expensive suites that
do not provide material assurance for the active change, while prohibiting
known test failures from becoming normalized repository debt.

This standard does not weaken acceptance criteria, required safeguards, or
release gates. It separates responsibility for a failure from the requirement
that the integrated candidate ultimately be green.

## 2. Governing Principles

Every mandatory test or validation command SHALL map to at least one of:

1. an explicit acceptance criterion;
2. changed behavior;
3. a direct or demonstrated transitive dependency;
4. a shared infrastructure surface changed by the work;
5. a named regression risk;
6. a merge, release, deployment, or production-readiness gate.

A suite SHALL NOT be made mandatory solely because it was used by an earlier
work item, appears in a generic evidence template, or has historically been run
by the implementing agent.

No branch may be declared merge-ready while a required safe repository test has
an unexplained or unresolved failure. A failure outside the current work item's
scope SHALL be tracked and corrected through a separately authorized work item;
it SHALL NOT be silently ignored, waived, or absorbed into the current scope.

## 3. Test Execution Stages

### 3.1 Inner loop

After a small edit, run the smallest test that can falsify the current claim:

- the failing node ID;
- one test class;
- one directly affected test file;
- a narrow lint, type, syntax, or import check on changed modules.

Do not run the full suite, broad domain bundles, or unrelated canaries after
every edit or conversational turn.

### 3.2 Coherent change validation

After completing a coherent implementation slice, run:

- directly affected test files;
- tests for direct callers and consumers when behavior crosses a boundary;
- changed-file lint and type checks where those tools govern the files;
- adversarial or invariant tests required by the acceptance criteria.

### 3.3 Candidate-commit validation

Before creating or updating a review candidate, run the complete work-item
acceptance suite defined by the approved plan or authorization, as modified by
any later operator-approved decision.

### 3.4 Committed-SHA checkpoint

At the final committed SHA, capture reproducible evidence for:

- the work-item acceptance suite;
- required static checks;
- required baseline comparison;
- conditionally applicable cross-domain canaries;
- repository state, command, environment, result, and evidence hash.

A costly suite normally runs once per materially different candidate SHA, not
once per agent turn.

### 3.5 Merge and release validation

The full safe repository suite is reserved for:

- merge or release readiness;
- broad cross-domain refactors;
- shared test infrastructure changes;
- changes to global fixtures, dependency configuration, packaging, or runtime
  bootstrap behavior;
- behavior reasonably capable of affecting unrelated areas.

Merge readiness requires zero unresolved failures in every suite required by the
merge gate. Deferred or separately assigned corrective work does not make a red
integrated candidate merge-ready.

## 4. Impact Classes

| Impact class | Typical changes | Required validation |
|---|---|---|
| Local | One function, module, or isolated policy | Targeted tests and changed-file static checks |
| Domain | Multiple files in one bounded domain | Domain-focused suite plus direct integration seams |
| Shared infrastructure | Migrator, schema bootstrap, common database layer, package configuration, global fixtures | Affected domain suites plus applicable cross-domain canaries |
| Cross-domain | Shared API, CLI, data contract, or refactor spanning domains | All affected domain suites and selected broader regression tests |
| Release | Merge, release, deployment, or production gate | Full safe suite and gate-specific evidence |

## 5. Forecasting and Schedule Bundles

### 5.1 Forecasting bundle

Run `scripts/test-forecasting.sh` when the change affects forecasting generation,
configuration, read models, readiness or semantic gates, forecasting API/UI,
forecast-related financial normalization, or shared infrastructure used by
those paths.

### 5.2 Schedule bundle

Run `scripts/test-schedule.sh` when the change affects schedule ingestion,
XER/XML/MSP parsing, schedule quality, CPM/critical-path logic, schedule
identity, mapping, schedule projections, schedule migrations, or shared
infrastructure used by those paths.

The schedule bundle is a cross-domain canary for changes to
`src/hb_assistant/store/migrator.py`, shared schema/bootstrap behavior, or other
verified common database infrastructure. It is not a default canary for
isolated source-index repository, connector, model, or service changes.

### 5.3 Both bundles

Run both bundles only when the change affects both domains or modifies shared
infrastructure with a demonstrated dependency into both domains.

## 6. Failure Classification

Every failing test SHALL be classified before corrective ownership is assigned.

| Classification | Required disposition |
|---|---|
| Candidate regression | The current implementing agent stops the affected checkpoint and fixes it within the active work item. |
| Reproducible pre-existing product defect | Preserve base and candidate evidence; create a separately authorized corrective work item. |
| Invalid or stale test | Create a bounded test-correction work item. Do not weaken, delete, or skip the test without evidence and review. |
| Flaky or nondeterministic test | Create a stabilization work item and preserve repeated-run evidence. |
| Environment or configuration failure | Correct or formally document the environment; do not label the product green from an invalid run. |
| Relationship unknown | Treat as potentially related and stop the affected checkpoint until causality is established. |

A failure is not "unrelated" merely because its filename or domain label differs
from the active objective. A pre-existing classification requires evidence that
the same failure reproduces on the immutable base SHA under a materially
equivalent command and environment, or equivalent direct causal evidence.

## 7. Parallel Corrective Work

A separate corrective agent MAY work in parallel while the primary agent
continues only when all of the following are true:

1. the failure is proven reproducible on the base SHA;
2. the failure does not invalidate the active work item's acceptance criteria or
   required evidence;
3. the corrective work has a bounded file and test surface;
4. primary and corrective agents have non-overlapping edit ownership;
5. the failure and correction do not involve shared schema, migrator/bootstrap,
   global fixtures, test discovery, dependency configuration, security controls,
   or another shared surface used by the primary work;
6. the corrective work uses a separate registered branch and, when local, a
   separate registered worktree;
7. the corrective work has a separate explicit authorization, evidence package,
   and independent review;
8. integration of the correction is separately authorized;
9. the combined candidate is rerun through all applicable checkpoint and merge
   gates.

The primary agent SHALL NOT create or activate a corrective sub-agent merely
because an unrelated failure was observed. It SHALL request or consume explicit
corrective authorization. The operator or deterministic controller owns the
parallel-work decision.

The primary agent SHALL pause rather than continue when the failure touches
shared infrastructure, overlaps candidate files, changes the meaning of current
acceptance evidence, or cannot be confidently classified.

## 8. No-Known-Failure Integration Rule

Focused testing is permitted during implementation, but the repository SHALL
not declare an integrated candidate merge-ready while any required safe test is
known to fail.

This means:

- zero unexplained failures;
- zero untracked pre-existing failures;
- zero required-suite failures at the integration gate;
- zero failure waivers based only on age or apparent domain distance.

It does not mean that the active implementing agent automatically receives
blanket authority to modify unrelated code. Unrelated failures remain blocking
repository debt with separate ownership, authorization, review, and evidence.

## 9. Evidence Reuse and Rerun Rules

Evidence MAY be reused when all of the following are unchanged and recorded:

- tested commit or immutable parent SHA;
- test command and selected targets;
- relevant dependency lock/configuration;
- interpreter and material environment fingerprint;
- fixtures or external inputs;
- expected purpose of the evidence.

Do not rerun a suite merely to reproduce an identical transcript during a
bookkeeping-only turn. Rerun when code, tests, dependencies, environment,
fixtures, command, acceptance criteria, or candidate SHA changed in a way that
could affect the result.

Parent-baseline evidence may be reused across corrective rounds when the parent
SHA and material environment remain identical. Reuse SHALL be declared in the
evidence manifest.

## 10. Plan and Authorization Requirements

Implementation plans and authorizations SHALL distinguish:

- `inner_loop_tests`;
- `candidate_tests`;
- `committed_checkpoint_tests`;
- `conditional_canaries` with explicit trigger conditions;
- `merge_or_release_tests`;
- failure-classification evidence;
- parallel corrective work, when authorized;
- final integrated-green requirements.

Each required suite SHALL include a short mapping to the acceptance criterion,
dependency, or regression risk it covers.

An approved historical plan SHALL not be silently rewritten. Use a superseding
plan revision or an explicit operator-approved decision.

## 11. Stop Conditions

An agent SHALL stop and report when:

- the approved plan and this standard conflict materially and no superseding
  operator decision exists;
- dependency or blast-radius evidence is unavailable for a high-risk change;
- a required suite cannot be executed;
- narrowing tests would weaken an explicit acceptance criterion or safeguard;
- a failure cannot be proven pre-existing;
- proposed parallel correction overlaps files, shared infrastructure, or
  acceptance evidence;
- the combined candidate remains red.

## 12. Reporting

Implementation and corrective reports SHALL state:

- tests executed and exact results;
- why each suite was selected;
- required tests not run and the reason;
- every failure classification and supporting base/candidate evidence;
- corrective work-item and branch identities when applicable;
- evidence reused and its immutable identity;
- broader suites deferred to a later gate;
- integrated-green status and residual unverified areas.
