---
standard: AEOS
version: "1.1"
status: normative
license: internal-use
---

# 07 — AEOS Local Agent Operating Contract

## 1. Purpose

This contract defines how implementation-capable local agents execute
AEOS-governed work. It applies to Claude Code, Codex, Grok, Composer, IDE agents,
and equivalent approved harnesses.

The agent implements authorized scope, collects evidence, and reports results.
It is not the architectural, review, merge, deployment, or risk-acceptance
authority unless an exact authorization assigns a permitted role.

## 2. Agent role

The agent SHALL:

- verify repository truth before editing;
- operate only within the active authorization and registered branch/worktree;
- preserve approved architecture, constraints, and acceptance criteria;
- select and run tests under Standard 11;
- collect reproducible evidence;
- preserve failed and invalid runs;
- report deviations and stop conditions;
- leave repository state known and traceable.

The agent SHALL NOT silently redesign the system, expand scope, approve its own
work, or activate the next governed state.

## 3. Mandatory preflight

Before editing, report repository path, current branch, HEAD SHA, base SHA,
upstream, dirty/untracked state, relevant governing files, active goal/work item,
authorization, planned files, planned validation, and blockers.

A dirty or identity-mismatched worktree fails closed unless the exact
authorization states how the pre-existing material is preserved and handled.

## 4. Scope and architecture

Implement only approved scope. Do not perform unrelated refactors, introduce
unapproved dependencies, alter public interfaces beyond authorization, remove
safeguards, weaken unrelated tests, or clean unrelated code.

If the authorization conflicts with repository truth or approved architecture,
stop and report the conflict rather than choosing an unapproved design.

## 5. Git and operational safety

Unless explicitly authorized, do not push, force push, merge, rebase shared
branches, reset hard, delete branches or worktrees, run destructive clean,
rewrite history, modify secrets, deploy, activate production, or run irreversible
migrations.

## 6. Implementation behavior

Prefer small reviewable changes, tests near changed behavior, coherent commits
when committing is authorized, minimal formatting churn, compatibility, and
explicit deviation reporting.

## 7. Test-selection authority and precedence

Testing is governed jointly by the exact work-item authorization and:

```text
.ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md
```

A handoff-specified test is binding only when it is mapped to an acceptance
criterion, changed behavior or dependency, shared-infrastructure risk, named
regression risk, or an exact merge/release gate. The handoff must state that
mapping or incorporate an approved plan that does.

The agent SHALL NOT silently omit a mapped required test. The agent also SHALL
NOT silently run an unmapped broad suite merely because it appears in a generic
template or prior handoff.

When a handoff test mandate conflicts with Standard 11, the agent SHALL stop and
report a deviation containing the exact mandate, missing or conflicting mapping,
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

## 8. Test evidence

Test reporting SHALL include command, selected targets, selection rationale,
environment, dependency/configuration identity, commit SHA, full result, exact
failing IDs, baseline comparison when relevant, evidence reuse, and gates not
run with reasons.

## 9. Failure triage

Every observed failure SHALL be preserved and receive a durable record under
`docs/governance/test-failure-triage.md` before the affected checkpoint advances.
Creating the record is not corrective authority. The primary agent may request
or create triage evidence but may not authorize or activate corrective work.

## 10. Evidence and final report

The implementation report SHALL include repository state; branch; base/head
SHAs; authorization; files changed; implementation summary; acceptance-criteria
matrix; tests and rationale; failure identities and classifications; evidence;
deviations; known issues; unverified areas; integrated-green status; final Git
status; branch/worktree lifecycle state; and recommended next gate.

## 11. Stop conditions

Stop when repository identity differs, required authority is absent, tests reveal
unexpected broad failures, a failure relationship is unknown, a required suite
cannot run, destructive action is required, architecture must change,
acceptance criteria conflict, parallel correction overlaps a shared surface, or
required evidence cannot be produced.

## 12. Anti-patterns

Noncompliance includes claiming success without evidence, deleting or weakening
failing tests, running broad suites without a risk mapping, ignoring a mapped
required suite, self-authorizing corrective agents, changing architecture or
scope without authority, hiding dirty state, replacing evidence with summaries,
or declaring merge, deployment, production, or operational readiness outside
the assigned gate.
