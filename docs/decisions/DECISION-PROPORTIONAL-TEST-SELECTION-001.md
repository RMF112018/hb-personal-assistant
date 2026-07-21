---
title: "Proportional Test Selection and No-Known-Failure Integration"
artifact_id: "DECISION-PROPORTIONAL-TEST-SELECTION-001"
classification: "Decisions"
artifact_type: "Operator Decision"
version: "1.1"
status: "Accepted"
date_created: "2026-07-21"
date_updated: "2026-07-21"
decision_owner: "Bobby Fetting"
author: "OpenAI ChatGPT, operator-directed"
repository: "RMF112018/hb-personal-assistant"
branch_pr_commit: "chore/proportional-test-selection-policy-v2 / base 8b44cbd216d531a1894b4257355469edf922029f / PR pending"
decision_scope: "Repository-wide test selection, failure disposition, parallel corrective work, and active permanent-identity goal test requirements"
supersedes:
  - "PI-WI-03 arc-plan blanket schedule-canary requirement, test-selection scope only"
superseded_by: []
related_artifacts:
  - ".ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md"
  - "AGENTS.md"
  - "CLAUDE.md"
  - "docs/testing/forecasting-and-schedule-test-bundles.md"
  - "GOAL-SOURCE-INDEX-PERMANENT-IDENTITY-CORRECTIVE-001"
tags:
  - testing
  - evidence
  - aeos
  - source-index
  - corrective-work
  - governance
---

# Proportional Test Selection and No-Known-Failure Integration

**Classification:** Decisions  
**Artifact Type:** Operator Decision  
**Version:** 1.1  
**Status:** Accepted

## Decision

The repository shall use proportional test selection and failure disposition
governed by `.ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md`.

Expensive suites and cross-domain canaries are required only when they map to an
acceptance criterion, changed dependency, shared infrastructure surface, named
regression risk, or merge/release gate. They are not required after every edit
or every agent turn.

No integrated candidate may be declared merge-ready while a required safe test
is known to fail. A proven pre-existing failure outside the active work item
must receive separate corrective ownership; it may not be ignored or silently
absorbed into the current scope.

## Active Permanent-Identity Goal

For `GOAL-SOURCE-INDEX-PERMANENT-IDENTITY-CORRECTIVE-001`, this decision
supersedes the PI-WI-03 arc plan's blanket instruction to run
`scripts/test-schedule.sh` for every unit, but only for test selection. It does
not alter architecture, feature scope, acceptance criteria, authorization
boundaries, review requirements, or prior evidence.

1. **PI-WI-02B schema/migrator work:** retain the schedule bundle as a
   committed-SHA cross-domain canary because the work changes the shared
   migrator/schema path.
2. **PI-WI-03a runtime re-key work:** the schedule bundle is not required when
   the diff remains confined to the authorized source-index repository,
   connector models/service, and directly related tests. It becomes required if
   the work changes shared migrator/schema/bootstrap code, schedule-domain code,
   or repository evidence demonstrates a schedule dependency.
3. **PI-WI-03b move-continuity work:** apply the same conditional rule. The
   source-index acceptance suite, move/drain tests, static guards, and direct
   integration seams remain mandatory; the schedule bundle is conditional.
4. **Final merge or release gate:** broader safe validation remains governed by
   the applicable readiness plan and must finish with zero unresolved required-
   suite failures.

## Failure Disposition

A failing test must be classified as one of: candidate regression, reproducible
pre-existing product defect, invalid or stale test, flaky or nondeterministic
test, environment/configuration failure, or relationship unknown.

A failure is considered pre-existing only when it reproduces on the immutable
base SHA under a materially equivalent command and environment, or equivalent
direct evidence establishes causality. Domain labels or filenames alone are not
sufficient.

Candidate regressions remain the responsibility of the active work item.
Unknown relationships block the affected checkpoint until resolved.

## Parallel Corrective Work

A separate corrective agent may work in parallel only under separate explicit
authorization and on a separately registered branch/worktree. Parallel work is
permitted only when:

- the failure is proven pre-existing;
- current acceptance evidence remains valid;
- edit ownership does not overlap;
- no shared schema, migrator/bootstrap, global fixture, test-discovery,
  dependency, security, or other common surface is involved;
- the corrective stream produces its own evidence and independent review;
- final integration is separately authorized and the combined candidate is
  rerun through applicable gates.

The primary agent may continue its bounded objective under those conditions,
but may not create or activate the corrective stream on its own authority.

## Execution Frequency

- Inner-loop validation uses the smallest relevant tests.
- Work-item candidate validation uses the complete bounded acceptance suite.
- Expensive canaries normally run once for each materially different committed
  candidate SHA when their trigger condition is satisfied.
- Bookkeeping-only turns do not rerun code tests when the tested SHA, command,
  dependencies, environment, and evidence purpose are unchanged.
- Parent-baseline evidence may be reused when its immutable SHA and material
  environment remain unchanged and reuse is declared.

## Historical Plan Preservation

Approved and reviewed historical plans remain unchanged for lineage. This
operator decision is the forward-applicable control for test selection and
failure disposition. Future plans and authorizations shall encode separate
inner-loop, candidate, checkpoint, conditional-canary, merge/release, failure-
classification, and final integrated-green requirements.

## Non-Effects

This decision does not:

- waive a failing test;
- authorize blanket correction of unrelated code;
- weaken an acceptance criterion or safeguard;
- authorize implementation outside a bounded work item;
- approve any implementation or corrective result;
- authorize merge, deployment, migration, production activation, cleanup, or
  risk acceptance;
- invalidate previously captured schedule-canary evidence.

## Required Follow-Through

Repository agent guidance, the AEOS master index, decision index, and testing
documentation shall reference the standard. New implementation plans shall map
every mandatory suite to an acceptance criterion, dependency, shared-
infrastructure risk, or release gate and shall define disposition for discovered
failures.
