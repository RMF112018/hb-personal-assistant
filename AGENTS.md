# AGENTS.md

This repository uses AEOS-governed AI-assisted software delivery across Claude
Code, Codex, Grok-based local harnesses, and other approved coding agents.

## Required Entry Point

Before substantive discovery, planning, review, audit, implementation,
corrective work, readiness assessment, or goal execution, read:

```text
.ai/project-sources/00_AEOS_MASTER_INDEX.md
```

Then read the governing sources selected for the active workflow mode.

For goal-driven loop work, also read:

```text
.ai/agent-skills/_aeos-shared/AEOS_SKILL_OPERATING_CONTRACT.md
.ai/aeos/goals/<goal-id>/goal-charter.md
.ai/aeos/goals/<goal-id>/state.yaml
```

and the exact current authorization and selected canonical skill.

## Authority Order

1. Current repository and runtime evidence.
2. Approved repository-specific specifications and acceptance criteria.
3. Repository-local ADRs, policies, and instructions.
4. AEOS governance under `.ai/project-sources/`.
5. Current operator instructions.
6. Prior conversations, summaries, or model memory.

Lower-authority material must not override higher-authority evidence.

## Engineering Control-Plane Authority

For `RMF112018/hb-personal-assistant`, the repository and GitHub are the
canonical engineering execution control plane:

- repository and GitHub records define the active goal pointer, work item,
  authorization pointer, branch, base SHA, head SHA, pull request, review state,
  merge state, and checkpoint identity;
- deployed runtime evidence is authoritative for operational and production
  behavior claims;
- the Google Drive Software Delivery Control Center is a publication,
  collaboration, reference, and external-handoff surface;
- Drive content must not independently override or authorize repository
  execution state;
- existing Drive artifacts remain historical evidence, but new Drive-native
  mechanisms that independently track active engineering execution state are
  frozen during the GitHub-first migration;
- final lifecycle authorization, risk acceptance, merge, deployment, and
  production activation remain operator decisions.

Independent review must identify the exact repository or pull-request head SHA
reviewed. A review of an earlier head is not current-head approval after the head
changes unless a governing policy explicitly establishes a narrower result.

The governing decision, lifecycle policy, and migration plan are:

```text
docs/decisions/ADR-019-github-first-engineering-control-plane.md
docs/governance/branch-worktree-lifecycle-policy.md
docs/implementation-plans/github-first-control-plane-migration.md
```

## Branch and Worktree Lifecycle

Every non-canonical branch and linked worktree must be associated with a
governed work item before substantive editing. The registration must identify
the worktree path, branch, base SHA, owner or agent, goal or work item, and
expected disposition.

A pull-request merge transitions the associated work to
`MERGED_PENDING_CLEANUP`; it does not make the work item operationally complete.
Closure requires verified disposition of the worktree, local branch, and remote
branch, together with a durable cleanup receipt or a recorded retention/blocker
decision.

Before cleanup, agents must prove that:

- the worktree is clean or all remaining material has been preserved and
  assigned;
- the branch tip is integrated, patch-equivalent, intentionally retained, or
  blocked from deletion;
- no running process or material evidence depends on the worktree path;
- cleanup is within the active authorization.

Agents must fail closed when evidence is incomplete. Routine hygiene must not
use `git reset --hard`, broad `git clean`, forced worktree removal, or
`git branch -D`. Local worktree removal, local branch deletion, and remote
branch deletion are separate governed actions.

## Canonical Agent Skills

The sole canonical AEOS skill corpus is:

```text
.ai/agent-skills/
```

Harness-specific surfaces are adapters only:

```text
~/.claude/skills/       # global Claude discovery links
.agents/skills/         # repository-local Codex discovery links
.ai/agent-harnesses/    # Claude, Codex, and Grok adapter guidance
```

Do not maintain independent edited copies of the AEOS skills in harness
directories. Harness adapters must not reinterpret or weaken canonical skill
requirements.

## Goal and Loop Discipline

For an AEOS-governed goal:

- the goal charter defines the destination;
- `state.yaml` defines the current lifecycle state;
- a validated operator authorization defines the work currently permitted;
- exactly one workflow state may be active in an invocation;
- the agent may complete the active state but may not authorize the next state;
- every state closes with a durable checkpoint package;
- external review and operator authorization are required before resumption;
- implementers do not certify their own plans or implementation;
- original finding identifiers and history remain traceable;
- a broad goal prompt is not blanket authorization for all lifecycle stages.

The deterministic controller or validated state—not the model—selects the active
workflow and skill.

## Agent Rules

Agents must:

- report repository path, branch, HEAD SHA, upstream when material, and worktree
  state before editing;
- identify the active goal, state, authorization, and work item;
- register any new non-canonical branch and worktree before substantive editing;
- preserve approved scope and architecture;
- distinguish verified facts, unverified claims, assumptions, unknowns, and
  unavailable evidence;
- produce evidence for implementation and readiness claims;
- run required tests or explain exactly why they were not run;
- report deviations before proceeding;
- preserve failed and invalid evidence runs;
- leave findings and disposition history traceable;
- complete or explicitly block the branch/worktree cleanup checkpoint;
- stop at the required checkpoint.

Agents must not, without explicit operator approval:

- push;
- force push;
- merge;
- rewrite history;
- delete branches or worktrees outside the accepted lifecycle policy and active
  authorization;
- delete remote branches unless separately authorized or covered by an accepted
  automatic-delete policy;
- reset hard;
- modify secrets or credentials;
- deploy or activate production services;
- run irreversible migrations;
- weaken tests, thresholds, evidence requirements, or safeguards;
- remove unrelated safeguards or tests;
- accept risk;
- approve their own plan or implementation;
- activate the next goal state;
- overwrite closed checkpoint evidence.

## Harness Role Separation

When multiple agents participate:

- the implementation context must not perform the independent audit;
- an audit context must not patch the implementation it is auditing;
- external model recommendations do not constitute operator authorization;
- corrective implementation may address only authorized findings;
- a model may recommend a next gate but may not approve it.

## Required Final Report

Implementation and corrective agents must provide:

1. Bounded disposition.
2. Repository path, branch, dirty state, and upstream status when material.
3. Base and head SHAs.
4. Active goal, state, authorization, checkpoint, and work item.
5. Files changed.
6. Implementation summary.
7. Acceptance-criteria matrix.
8. Tests executed and exact results.
9. Evidence paths and hashes.
10. Deviations.
11. Known issues, residual risks, and unverified areas.
12. Final Git status.
13. Branch/worktree lifecycle state and cleanup, retention, or blocker receipt.
14. Recommended next gate.

A recommendation is not an authorization.
