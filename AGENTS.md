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

## Test Selection and Failure Disposition

All agents must read and follow:

```text
.ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md
docs/decisions/DECISION-PROPORTIONAL-TEST-SELECTION-001.md
```

Testing must be proportional to the active objective and demonstrated blast
radius. Every mandatory suite must map to an acceptance criterion, changed
behavior or dependency, shared-infrastructure risk, named regression risk, or
merge/release gate. Do not run broad suites or unrelated canaries after every
edit or agent turn.

Every failure must be preserved and classified. A failure may be treated as
pre-existing only when it reproduces on the immutable base SHA under a
materially equivalent command and environment, or equivalent direct evidence
establishes causality. A filename or domain label is not sufficient.

A candidate regression remains in the active work item. A proven pre-existing
failure requires a separately authorized corrective work item. Parallel
correction requires a separately registered branch/worktree, non-overlapping
edit ownership, separate evidence and review, and no shared schema, migrator,
global-fixture, dependency, security, or other common-surface conflict. The
primary agent may not self-authorize or activate that corrective stream.

Focused implementation may continue under those conditions, but no integrated
candidate is merge-ready while a required safe test has an unresolved failure.

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
- independent review by an eligible reviewer subagent or other approved external
  review context, followed by operator authorization, is required before
  resumption;
- implementers do not certify their own plans or implementation;
- original finding identifiers and history remain traceable;
- a broad goal prompt is not blanket authorization for all lifecycle stages.

The deterministic controller or validated state—not the model—selects the active
workflow and skill.

## Mandatory Subagent Review and Approval

When the active harness supports subagents, substantive planning,
implementation, corrective work, audit preparation, and readiness assessment
must use a fresh reviewer subagent before the parent context claims that the
artifact or candidate is ready for the next gate.

The parent or implementation context must:

- finish and freeze the review candidate before spawning the reviewer;
- provide a bounded review brief containing the goal and work-item identity,
  acceptance criteria, exact base and head SHA or immutable artifact identity,
  changed scope, relevant tests and evidence paths, known deviations, and the
  requested decision;
- spawn the reviewer in a fresh context that did not participate in planning or
  implementation and provide no implementer chain-of-thought, preferred
  conclusion, or patch instructions;
- keep the reviewer read-only and require independent inspection of the diff,
  repository truth, tests, and evidence rather than accepting the parent
  context's summary as proof;
- preserve the reviewer findings and disposition without suppression or
  favorable rewriting;
- route required corrections back to an implementation context, then obtain a
  new review against the corrected exact identity;
- invalidate the approval after any material commit, artifact mutation, or
  evidence change; and
- add specialist reviewer subagents proportional to risk, including test,
  security/privacy, migration/data, architecture, or evidence/readiness review
  when those surfaces are material.

A reviewer or approver subagent:

- must not have authored, edited, or materially directed the work under review;
- must not patch the candidate it is reviewing;
- may issue only a bounded artifact-level disposition such as `APPROVE`,
  `APPROVE_WITH_NONBLOCKING_FINDINGS`, `REQUEST_CHANGES`, `BLOCKED`, or
  `INSUFFICIENT_EVIDENCE`;
- must identify the exact SHA or immutable artifact identity reviewed;
- must report the acceptance-criteria result, findings, evidence gaps, residual
  risks, and unverified areas;
- must not waive acceptance criteria, conceal findings, or treat parent-agent
  narrative as evidence; and
- must not authorize a lifecycle transition, push, merge, cleanup, deployment,
  production activation, destructive action, credential change, or risk
  acceptance.

For a formal AEOS independent decision, a subagent qualifies only when it is a
fresh, distinct execution context, did not participate in producing the work,
remains read-only, reviews the exact candidate identity, and the governing
workflow permits that reviewer class. The subagent's artifact-level approval is
review evidence; it is never operator authorization. If the harness cannot
establish an eligible independent subagent context, stop at the applicable
ready-for-review disposition and obtain another approved review context.

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
- delegate substantive review and artifact-level approval to an eligible fresh
  reviewer subagent when the harness supports subagents;
- select tests under the repository test-selection standard;
- run required tests or explain exactly why they were not run;
- classify and preserve every observed failure;
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
- waive, hide, or silently ignore a failing required test;
- expand the active work item to correct unrelated failures;
- remove unrelated safeguards or tests;
- accept risk;
- approve their own plan or implementation;
- activate the next goal state;
- overwrite closed checkpoint evidence.

## Harness Role Separation

When multiple agents participate:

- the implementation context must not perform the independent audit;
- a fresh eligible reviewer subagent may approve the reviewed artifact within
  its bounded decision scope but may not authorize the next lifecycle state or
  any operator-only action;
- an audit context must not patch the implementation it is auditing;
- external model or subagent recommendations do not constitute operator
  authorization;
- corrective implementation may address only authorized findings;
- parallel failure correction requires a separate work item, authorization,
  registered branch/worktree, evidence package, and review context;
- the parent context must not replace, dilute, or override a reviewer
  disposition; and
- a model may recommend a next gate, but only the operator may authorize it.

## Required Final Report

Implementation and corrective agents must provide:

1. Bounded disposition.
2. Repository path, branch, dirty state, and upstream status when material.
3. Base and head SHAs.
4. Active goal, state, authorization, checkpoint, and work item.
5. Files changed.
6. Implementation summary.
7. Acceptance-criteria matrix.
8. Tests executed, selection rationale, and exact results.
9. Failure classifications and base/candidate evidence.
10. Corrective work-item and branch identities when applicable.
11. Evidence paths and hashes.
12. Deviations.
13. Known issues, residual risks, and unverified areas.
14. Integrated-green status.
15. Final Git status.
16. Branch/worktree lifecycle state and cleanup, retention, or blocker receipt.
17. Reviewer subagent identity or role, reviewed SHA or artifact identity,
    disposition, findings, and evidence location.
18. Recommended next gate.

A recommendation or subagent approval is not operator authorization.
