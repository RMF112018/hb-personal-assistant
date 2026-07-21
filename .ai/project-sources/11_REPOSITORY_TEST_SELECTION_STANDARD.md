---
standard: AEOS
version: "1.0"
status: normative
license: internal-use
---

# 11 — Repository Test Selection Standard

## 1. Purpose

This standard defines proportional, evidence-oriented test selection for
`RMF112018/hb-personal-assistant`. It prevents both under-testing and repeated
execution of expensive suites that do not provide material assurance for the
change under review.

This standard does not weaken acceptance criteria, required safeguards, or
release gates. It determines when a test suite is relevant and when previously
captured evidence may be reused.

## 2. Governing Principle

Every mandatory test or validation command SHALL map to at least one of:

1. an explicit acceptance criterion;
2. changed behavior;
3. a direct or demonstrated transitive dependency;
4. a shared infrastructure surface changed by the work;
5. a named regression risk;
6. a merge, release, deployment, or production-readiness gate.

A suite SHALL NOT be made mandatory solely because it was used by an earlier
work item, appears in a generic evidence template, or is inexpensive relative
to another suite.

## 3. Test Execution Stages

### 3.1 Inner loop

After a small edit, run the smallest test that can falsify the current claim:

- the failing node ID;
- one test class;
- one directly affected test file;
- a narrow lint, type, syntax, or import check on changed modules.

Do not run the full suite, broad domain bundles, or unrelated canaries after
every edit.

### 3.2 Coherent change validation

After completing a coherent implementation slice, run:

- directly affected test files;
- tests for direct callers and consumers when behavior crosses a boundary;
- changed-file lint and type checks where those tools govern the files;
- any adversarial or invariant tests required by the acceptance criteria.

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
once per conversational turn.

### 3.5 Merge and release validation

The full safe repository suite is reserved for:

- merge or release readiness;
- broad cross-domain refactors;
- shared test infrastructure changes;
- changes to global fixtures, dependency configuration, packaging, or runtime
  bootstrap behavior;
- behavior reasonably capable of affecting unrelated domains.

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

## 6. Evidence Reuse and Rerun Rules

Evidence MAY be reused when all of the following are unchanged and recorded:

- tested commit or immutable parent SHA;
- test command and selected targets;
- relevant dependency lock/configuration;
- interpreter and material environment fingerprint;
- fixtures or external inputs;
- expected purpose of the evidence.

Do not rerun a suite merely to reproduce an identical transcript during a
bookkeeping-only turn. Rerun when code, tests, dependencies, environment,
fixtures, command, acceptance criteria, or the candidate SHA changed in a way
that could affect the result.

Parent-baseline evidence may be reused across corrective rounds when the parent
SHA and material environment remain identical. The reuse SHALL be declared in
the evidence manifest.

## 7. Plan and Authorization Requirements

Implementation plans and authorizations SHALL distinguish:

- `inner_loop_tests`;
- `candidate_tests`;
- `committed_checkpoint_tests`;
- `conditional_canaries` with explicit trigger conditions;
- `merge_or_release_tests`.

Each required suite SHALL include a short mapping to the acceptance criterion,
dependency, or regression risk it covers.

A plan that requires an unrelated suite without such a mapping SHOULD be
revised before implementation. An already approved historical plan SHALL not
be silently rewritten; use a superseding plan revision or an explicit
operator-approved decision.

## 8. Exceptions and Stop Conditions

An agent SHALL run a broader suite when repository evidence reveals a larger
blast radius than expected. The agent SHALL report the reason before treating
the broader suite as mandatory for later turns.

An agent SHALL stop and report when:

- the approved plan and this standard conflict materially and no superseding
  operator decision exists;
- dependency or blast-radius evidence is unavailable for a high-risk change;
- a required suite cannot be executed;
- narrowing the tests would weaken an explicit acceptance criterion or
  safeguard.

## 9. Reporting

The implementation report SHALL state:

- tests executed and exact results;
- why each suite was selected;
- required tests not run and the reason;
- evidence reused and its immutable identity;
- broader suites deferred to a later gate;
- residual unverified areas.
