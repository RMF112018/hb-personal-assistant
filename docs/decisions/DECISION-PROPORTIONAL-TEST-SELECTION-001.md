---
title: "Proportional Test Selection and Evidence Reuse"
artifact_id: "DECISION-PROPORTIONAL-TEST-SELECTION-001"
classification: "Decisions"
artifact_type: "Operator Decision"
version: "1.0"
status: "Accepted"
date_created: "2026-07-21"
date_updated: "2026-07-21"
decision_owner: "Bobby Fetting"
author: "OpenAI ChatGPT, operator-directed"
repository: "RMF112018/hb-personal-assistant"
branch_pr_commit: "chore/proportional-test-selection-policy / PR pending"
decision_scope: "Repository-wide test selection; active permanent-identity goal test requirements"
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
  - governance
---

# Proportional Test Selection and Evidence Reuse

**Classification:** Decisions  
**Artifact Type:** Operator Decision  
**Version:** 1.0  
**Status:** Accepted

## Decision

The repository shall use proportional test selection governed by
`.ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md`.

Expensive test suites and cross-domain canaries are required only when they map
to an acceptance criterion, changed dependency, shared infrastructure surface,
named regression risk, or merge/release gate. They are not required after every
edit or every agent turn.

## Active Permanent-Identity Goal

For `GOAL-SOURCE-INDEX-PERMANENT-IDENTITY-CORRECTIVE-001`, this decision
supersedes the PI-WI-03 arc plan's blanket instruction to run
`scripts/test-schedule.sh` for every unit, but only for test selection. It does
not alter architecture, scope, acceptance criteria, authorization boundaries,
review requirements, or prior evidence.

The following rules apply:

1. **PI-WI-02B schema/migrator work:** retain the schedule bundle as a
   committed-SHA cross-domain canary because the work changes the shared
   migrator/schema path.
2. **PI-WI-03a runtime re-key work:** the schedule bundle is not required when
   the diff remains confined to the authorized source-index repository,
   connector models/service, and directly related tests. Run it only if the
   work changes shared migrator/schema/bootstrap code, schedule-domain code, or
   repository evidence demonstrates a schedule dependency.
3. **PI-WI-03b move-continuity work:** apply the same conditional rule. The
   source-index acceptance suite, move/drain tests, static guards, and direct
   integration seams remain mandatory; the schedule bundle is conditional.
4. **Final merge or release gate:** broader repository validation may still
   require the full safe suite or additional canaries under the applicable
   readiness plan.

## Execution Frequency

- Inner-loop validation uses the smallest relevant tests.
- Work-item candidate validation uses the complete bounded acceptance suite.
- Expensive canaries normally run once for each materially different committed
  candidate SHA when their trigger condition is satisfied.
- Bookkeeping-only turns do not rerun code tests when the tested SHA, command,
  dependencies, environment, and evidence purpose are unchanged.
- Parent-baseline evidence may be reused when its immutable SHA and material
  environment remain unchanged and the reuse is declared.

## Historical Plan Preservation

Approved and reviewed historical plans remain unchanged for lineage. This
operator decision is the forward-applicable control for test selection. Future
plan revisions and authorizations shall encode separate inner-loop,
candidate-commit, checkpoint, conditional-canary, and merge/release test sets.

## Non-Effects

This decision does not:

- waive a failing test;
- weaken an acceptance criterion or safeguard;
- authorize implementation outside an existing work-item scope;
- approve any implementation or corrective result;
- authorize merge, deployment, migration, production activation, or risk
  acceptance;
- invalidate previously captured schedule-canary evidence.

## Required Follow-Through

Repository agent guidance and testing documentation shall reference the new
standard. New implementation plans shall map every mandatory suite to an
acceptance criterion, dependency, shared-infrastructure risk, or release gate.
