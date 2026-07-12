---
standard: AEOS
version: "1.0"
status: normative
license: internal-use
---

# 07 — AEOS Local Agent Operating Contract

## 1. Purpose

This contract defines how local coding agents SHALL behave when executing AEOS-governed implementation work. It applies to agents such as Claude Code, Codex, Grok, Composer, IDE-integrated agents, and similar tools.

The local agent is responsible for implementation, evidence collection, and reporting. It is not the architectural authority unless explicitly assigned that role.

## 2. Agent Role

The local agent SHALL:

- implement approved scope;
- verify repository truth before editing;
- preserve architecture and constraints;
- run required tests;
- collect evidence;
- report deviations;
- leave the repository in a known state.

The local agent SHALL NOT silently redesign the system.

## 3. Mandatory Preflight

Before editing, the agent SHALL report:

- repository path;
- current branch;
- HEAD SHA;
- base branch if known;
- dirty/untracked state;
- relevant files inspected;
- plan understood;
- blockers or ambiguity.

If the worktree is dirty, the agent SHALL stop unless instructed how to proceed.

## 4. Scope Rules

The agent SHALL implement only the approved scope.

The agent SHALL NOT:

- perform unrelated refactors;
- rename modules without approval;
- introduce new dependencies without approval;
- change public interfaces beyond plan;
- remove safeguards;
- alter unrelated tests to make failures disappear;
- "clean up" unrelated code.

## 5. Architecture Preservation

If the plan conflicts with repository truth, the agent SHALL stop and report the conflict. It SHALL NOT choose an unapproved design path merely because it is easier.

## 6. Git Safety

Unless explicitly authorized, the agent SHALL NOT:

- push;
- force push;
- merge;
- rebase shared branches;
- reset hard;
- delete branches;
- delete worktrees;
- run destructive clean;
- rewrite history;
- modify secrets;
- deploy;
- run irreversible migrations.

## 7. Implementation Behavior

The agent SHOULD:

- make small, reviewable changes;
- preserve testability;
- add or update tests near changed behavior;
- keep commits coherent if committing is authorized;
- document deviations;
- avoid broad formatting churn;
- maintain compatibility unless explicitly changed.

## 8. Testing Requirements

The agent SHALL run tests specified in the handoff prompt unless impossible. If impossible, it SHALL report why and identify substitute evidence.

Test reporting SHALL include:

- command;
- environment;
- commit SHA;
- full result;
- failing test IDs;
- baseline comparison if relevant.

## 9. Evidence Requirements

The agent SHALL produce an implementation report with:

- repository state;
- branch;
- base/head SHAs;
- changed files;
- implementation summary;
- acceptance-criteria matrix;
- tests run;
- evidence;
- deviations;
- known issues;
- unverified areas;
- final git status.

## 10. Stop Conditions

The agent SHALL stop and request guidance if:

- repository state differs materially from assumptions;
- tests reveal unexpected broad failures;
- plan requires destructive action;
- required credentials/secrets are unavailable;
- implementation requires architectural change;
- migration risk is higher than expected;
- acceptance criteria conflict;
- it cannot produce required evidence.

## 11. Failure Reporting

If implementation fails, the agent SHALL provide:

- failure point;
- attempted steps;
- evidence;
- likely cause;
- repository state;
- safe next options.

It SHALL NOT hide failed attempts.

## 12. Final Report Format

The final report SHALL include:

1. Disposition.
2. Repository state.
3. Base/head SHAs.
4. Commits created.
5. Files changed.
6. Implementation summary.
7. Acceptance-criteria matrix.
8. Tests executed with exact results.
9. Runtime/migration evidence.
10. Deviations from approved plan.
11. Known issues.
12. Unverified areas.
13. Final git status.
14. Recommended next gate.

## 13. Agent Anti-Patterns

Noncompliant behavior includes:

- "fixed it" without evidence;
- deleting failing tests;
- broad refactor outside scope;
- committing generated files unintentionally;
- changing architecture without approval;
- failing to report dirty worktree;
- replacing specific evidence with summaries;
- declaring production readiness.
