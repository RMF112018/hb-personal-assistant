# AI Operating Manual

This repository is operated under AEOS across approved local and frontier-model
software-delivery harnesses.

## Start Here

Read:

```text
.ai/project-sources/00_AEOS_MASTER_INDEX.md
```

The Master Index routes the task to the governing AEOS standards.

Then read repository-root `AGENTS.md` and the harness-specific entrypoint or
adapter.

## Repository-Specific Rule

Repository truth overrides generic AEOS guidance. If current implementation,
approved specifications, ADRs, or repository policy conflict with generic
guidance, report the conflict and follow the higher-authority source.

## GitHub-First Engineering Control Plane

The repository and GitHub are canonical for engineering execution state.
Google Drive remains an approved publication, collaboration, reference, and
external-handoff surface.

Authority is separated as follows:

1. **Engineering execution authority** — repository content and GitHub issues,
   branches, commits, pull requests, reviews, and required checks.
2. **Runtime authority** — the deployed environment and runtime-generated
   evidence for operational claims.
3. **Publication/reference authority** — the Google Drive Software Delivery
   Control Center and other approved publication surfaces.
4. **Final decision authority** — the operator.

For repository-specific work, a Drive document must not independently redefine
or authorize the active work item, branch, SHA, pull request, review state,
merge state, or checkpoint. Existing Drive records remain historical evidence.
New Drive-native mechanisms that independently track active engineering
execution state are frozen during the migration defined by:

```text
docs/decisions/ADR-019-github-first-engineering-control-plane.md
docs/governance/branch-worktree-lifecycle-policy.md
docs/implementation-plans/github-first-control-plane-migration.md
```

Independent review must record the exact head SHA reviewed. A head change makes
the previous review stale for current-head approval unless the governing policy
explicitly states otherwise.

## Branch and Worktree Closeout

Branches and worktrees are governed execution records, not disposable agent
scratch space.

Every non-canonical worktree must be registered to a goal or work item before
substantive editing. Registration includes its path, branch, base SHA, owner or
agent, issue or pull request when available, and expected disposition.

A merge moves the associated work to `MERGED_PENDING_CLEANUP`. It does not move
the work item directly to `CLOSED`. Closure requires:

1. post-merge validation or an explicit not-required decision;
2. preservation or disposition of all dirty and untracked material;
3. proof that the branch is integrated, patch-equivalent, retained, or blocked;
4. verified worktree disposition;
5. verified local branch disposition;
6. verified or explicitly deferred remote branch disposition;
7. a durable cleanup, retention, or blocker receipt.

Normal cleanup must fail closed and avoid destructive shortcuts. `git reset
--hard`, broad `git clean`, forced worktree removal, and `git branch -D` are not
routine hygiene mechanisms. Remote branch deletion is a separate governed
action from local branch or worktree cleanup.

## Control-Plane Layout

```text
.ai/project-sources/       canonical AEOS governance
.ai/agent-skills/          canonical cross-harness skill corpus
.ai/agent-harnesses/       thin Claude, Codex, and Grok adapters
.ai/aeos/goals/            goal state, checkpoints, reviews, authorizations
.ai/aeos/bin/              deterministic control and validation utilities
.ai/schemas/               AEOS and goal-loop schemas
.ai/templates/             governing artifact and goal-loop templates
.ai/reference-bundles/     non-canonical convenience bundles
```

Harness discovery surfaces:

```text
~/.claude/skills/          global Claude links to canonical skills
.agents/skills/            repository Codex links to canonical skills
```

Do not duplicate or independently edit canonical skill content in these
discovery surfaces.

## Goal-Control Model

A governed goal uses:

1. a durable goal charter;
2. an explicit lifecycle state;
3. an operator-issued authorization;
4. one selected workflow skill;
5. required artifacts and evidence;
6. a checkpoint that terminates the invocation;
7. external review;
8. operator authorization for the next transition.

The model may execute only the currently authorized state. It may request but
must not activate the next state.

## Standard Goal Lifecycle

```text
Governance Initialization
→ Repository Truth
→ External Review
→ Architecture, when required
→ External Review
→ Implementation Planning
→ Independent Plan Review
→ Implementation
→ Independent Implementation Audit
→ Authorized Corrective Implementation
→ Independent Corrective Audit
→ Merge Authorization
→ Post-Merge Validation
→ Branch and Worktree Cleanup
→ Bounded Closure or Readiness Assessment
```

Stages may repeat only through explicit, traceable authorization.

## Artifact Locations

Repository engineering artifacts remain under the established locations:

```text
docs/architecture/
docs/decisions/
docs/governance/
docs/specs/
docs/implementation-plans/
docs/evidence/
docs/audits/
docs/go-no-go/
```

Goal-control records live under:

```text
.ai/aeos/goals/<goal-id>/
```

Goal-control records coordinate delivery; they do not replace authoritative
implementation evidence under `docs/evidence/`.

Google Drive publication copies must identify the canonical repository path,
issue, pull request, and SHA when those identities exist. Publication success or
failure does not mutate canonical engineering state.

## Evidence and Trust

- Agent summaries are not proof.
- Evidence must correspond to the reported repository SHA and environment.
- Independent review must identify the exact reviewed SHA.
- Preserve commands, exit codes, outputs, metrics, hashes, and limitations.
- Failed and invalid attempts remain part of the engineering record.
- Merge, deployment, production, and operational readiness are separate
  decisions.
- Branch/worktree cleanup is a separate closeout gate after merge.
- No agent may accept risk on behalf of the operator.

## Workflow Summary

```text
Discovery
→ Repository Truth
→ Architecture
→ Implementation Plan
→ Plan Review
→ Implementation
→ Evidence
→ Independent Audit
→ Corrective Review
→ Merge Authorization
→ Post-Merge Validation
→ Branch and Worktree Cleanup
→ Production Readiness
→ Go/No-Go
→ Explicitly Authorized Deploy
```
