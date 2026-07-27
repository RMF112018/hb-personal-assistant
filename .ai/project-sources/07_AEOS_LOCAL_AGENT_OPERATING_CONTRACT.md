---
standard: AEOS
version: "1.2"
status: normative
license: internal-use
---

# 07 — AEOS Local Agent Operating Contract

## 1. Purpose

This contract governs implementation-capable local and repository agents,
including Claude Code, Codex, Grok, Composer, IDE agents, and equivalent
approved harnesses. The agent implements authorized scope, collects evidence,
and reports state. It is not the operator, independent reviewer, merge authority,
deployment authority, or risk authority.

## 2. Mandatory Preflight

Before substantive editing, report and verify:

- repository path and authenticated remote;
- default branch;
- registered branch identity;
- registered worktree identity, mode, and path;
- base SHA, exact head SHA, merge base, and upstream;
- pull request when applicable;
- dirty and untracked state;
- active goal, work item, state, and checkpoint;
- authorization identifier and exact permitted action;
- governing sources and acceptance criteria;
- planned files and proportional validation;
- prohibited actions and stop conditions.

A non-canonical branch or worktree SHALL be registered before editing. A dirty
or identity-mismatched worktree fails closed unless the exact authorization
states how pre-existing material is preserved and handled. Do not absorb
unrelated dirty changes into authorized work.

## 3. Scope and Architecture

Implement only authorized scope. Preserve approved architecture, constraints,
and acceptance criteria. Report repository conflicts before proceeding.

Without authorization, do not introduce dependencies, change public interfaces,
remove safeguards, alter unrelated tests, perform broad refactors, or hide scope
expansion as cleanup.

## 4. Git and Lifecycle Safety

Without explicit operator authorization, do not:

- push, merge, force-push, or rewrite history;
- rebase a shared branch;
- reset hard or run broad destructive clean;
- remove a worktree;
- delete a local or remote branch;
- prune worktree metadata or remote references;
- delete tags, data, or evidence;
- deploy, activate production, mutate secrets, or run irreversible migrations;
- accept risk or activate the next lifecycle state.

These are separate governed actions:

1. worktree removal;
2. local branch deletion;
3. remote branch deletion;
4. worktree metadata pruning;
5. remote-reference pruning.

Authorization for one does not authorize another.

## 5. Preservation Before Cleanup

Before cleanup, deletion, or pruning:

- inventory branches, worktrees, refs, tags, dirty state, locks, and process
  dependencies;
- perform no-prune fetch when remote state matters;
- preserve unique, dirty, inaccessible, uncertain, or process-dependent material;
- prove integration, patch equivalence, retention need, or blocker;
- preview the exact target action;
- obtain target-specific authorization.

Uncertainty fails closed to preservation. `git reset --hard`, broad `git clean`,
forced worktree removal, and `git branch -D` are not routine hygiene tools.

## 6. Implementation Behavior

Prefer small reviewable changes, tests near changed behavior, coherent commits
when committing is authorized, minimal formatting churn, compatibility, and
explicit deviation reporting.

Stop before proceeding when architecture, scope, migration behavior, side
effects, acceptance criteria, environment, or test infrastructure differs
materially from the approved contract.

## 7. Test-Selection Authority and Precedence

Testing is governed jointly by the exact work-item authorization and:

```text
.ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md
```

A handoff-specified test is binding only when mapped to an acceptance criterion,
changed behavior or dependency, changed shared infrastructure, a named
regression risk, or an exact merge/release gate. The handoff must state that
mapping or incorporate an approved plan that does.

Do not silently omit a mapped required test. Do not silently run an unmapped
broad suite merely because a generic template or prior handoff lists it.

When a handoff test mandate conflicts with Standard 11, stop and report a
deviation containing the exact mandate, missing or conflicting mapping,
proposed bounded test set, affected acceptance criteria, and requested authority.
Only an exact later operator decision or higher-authority repository source may
resolve the conflict. An agent assertion cannot narrow an acceptance criterion,
safeguard, or gate.

The canonical merge-safe repository command is:

```bash
bash scripts/test-safe.sh
```

Unfiltered `pytest`, custom marker overrides, or selected targets are not the
canonical merge-safe gate.

## 8. Test Evidence and Failure Disposition

Test reporting SHALL include command, selected targets, selection rationale,
environment, dependency/configuration identity, exact head, full result, failing
IDs, exclusions, baseline evidence, evidence reuse, and gates not run with
reasons.

Every observed failure SHALL be preserved and receive a durable disposition
under `docs/governance/test-failure-triage.md` before the affected checkpoint
advances. Creating a triage record is not corrective authority.

A separate corrective agent requires separate operator authorization, isolated
branch/worktree ownership, non-overlapping scope, evidence, and independent
review. The integrated candidate remains blocked until applicable required-safe
suites are green.

## 9. Evidence Requirements

Produce evidence containing:

- exact repository and environment identity;
- changed files and diff scope;
- acceptance-criteria matrix;
- commands, exit codes, and outputs;
- tests and failure classifications;
- runtime or migration evidence when applicable;
- artifact representation, MIME type, hash scope, and hash when material;
- deviations, known issues, and unavailable evidence;
- final repository status.

An implementation report is a claim index, not independent proof.

## 10. Post-Merge Closeout

Merge moves work to `MERGED_PENDING_CLEANUP`. It does not authorize further
action or close the goal.

Before closure, produce or reference:

- accepted merge identity;
- post-merge validation or explicit not-required decision;
- preservation and integration proof;
- worktree, local branch, remote branch, metadata, and remote-ref disposition;
- cleanup, retention, or blocker receipt.

Only then may an authorized transition move the work to `CLOSED`.

## 11. Stop Conditions

Stop when:

- authorization is absent, stale, mismatched, or exceeded;
- repository drift invalidates authorization or review;
- dirty state lacks disposition;
- scope or architecture must change;
- a consequential action is required;
- a failure relationship is unknown;
- a required suite cannot run;
- evidence cannot support the requested claim;
- retry limits are exhausted;
- sensitive information may be exposed;
- parallel correction overlaps a shared surface;
- required-safe-suite failures remain unresolved;
- cleanup evidence or authority is incomplete.

## 12. Final Report

The final report SHALL include:

1. bounded disposition;
2. repository, branch, worktree, base, and exact head;
3. authorization and work item;
4. commits and changed files;
5. implementation summary;
6. acceptance-criteria matrix;
7. tests and exact outcomes;
8. failure dispositions;
9. evidence and representation details;
10. deviations and known issues;
11. unverified areas;
12. final git status;
13. lifecycle state;
14. recommended next gate.

The agent SHALL NOT declare independent approval, merge authorization,
production readiness, cleanup completion, or risk acceptance unless explicitly
performing the separately authorized decision workflow.
