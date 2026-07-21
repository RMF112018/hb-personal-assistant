# AI Operating Manual

This repository is operated under AEOS across approved local and frontier-model
software-delivery harnesses.

## Start Here

Read:

```text
.ai/project-sources/00_AEOS_MASTER_INDEX.md
```

The Master Index routes the task to the governing AEOS standards, including the
repository test-selection standard introduced by PR #319.

Then read repository-root `AGENTS.md` and the harness-specific entrypoint or
adapter.

## Repository-Specific Rule

Repository truth overrides generic AEOS guidance. If current implementation,
approved specifications, ADRs, repository policy, or authenticated GitHub state
conflict with generic guidance, report the conflict and follow the
higher-authority source.

## Truth Precedence and Action Authority

Factual truth and action authority are separate.

Use this factual precedence:

1. authenticated runtime evidence for deployed behavior;
2. authenticated repository and GitHub state for engineering identity and
   lifecycle;
3. repository-local governance, accepted ADRs, approved specifications, and
   acceptance criteria;
4. AEOS standards and approved publication/reference governance;
5. prior conversations and agent reports as claim indexes;
6. model memory or general knowledge.

The current operator instruction defines task intent and permitted scope. It
does not alter factual evidence, approve work by implication, or transfer risk
authority to a model. Workspace access, publication status, a prior approval,
or tool capability does not authorize a consequential action.

## GitHub-First Engineering Control Plane

The repository and GitHub are canonical for engineering execution state.
Runtime evidence is canonical for deployed behavior. Google Drive remains an
approved publication, collaboration, reference, and external-handoff surface.
The operator retains final decision, authorization, and risk authority.

For repository-specific work, a Drive document must not independently redefine
or authorize the active goal, work item, authorization, branch, worktree, base
SHA, head SHA, pull request, required-check state, review state, merge state, or
checkpoint. Drive records may publish or reference those identities but must
not become a competing active-state ledger.

The governing repository controls are:

```text
docs/decisions/ADR-019-github-first-engineering-control-plane.md
docs/governance/branch-worktree-lifecycle-policy.md
docs/implementation-plans/github-first-control-plane-migration.md
```

ADR-019 Phase A is merged at
`8b44cbd216d531a1894b4257355469edf922029f`. The lifecycle remains
`MERGED_PENDING_CLEANUP`; cleanup requires separate operator authorization and
evidence. Phase B remains separately unauthorized. Drive-native competing
engineering-state trackers are prohibited as an ongoing control.

Independent review must record the exact head SHA reviewed. A head change makes
the previous review stale for current-head approval unless the reviewer
explicitly reviews the new identity.

## Branch and Worktree Closeout

Branches and worktrees are governed execution records, not disposable agent
scratch space.

Every non-canonical branch and worktree must receive a stable registration
before substantive editing. Registration includes its identity, path when
local, branch, base SHA, current head, owner or agent, issue or work item,
authorization, expected disposition, and lifecycle history.

A merge moves the associated work to `MERGED_PENDING_CLEANUP`. It does not move
the work item directly to `CLOSED`. Closure requires:

1. post-merge validation or an explicit not-required decision;
2. preservation or disposition of all dirty and untracked material;
3. proof that the branch is integrated, patch-equivalent, retained, or blocked;
4. verified worktree disposition;
5. verified local-branch disposition;
6. verified or explicitly deferred remote-branch disposition;
7. a durable cleanup, retention, or blocker receipt.

Inventory, no-prune fetch, preservation, and integration proof must precede
pruning or deletion. Worktree removal, local-branch deletion, remote-branch
deletion, worktree metadata pruning, and remote-reference pruning are separate
governed actions.

Normal cleanup must fail closed and avoid destructive shortcuts. `git reset
--hard`, broad `git clean`, forced worktree removal, and `git branch -D` are not
routine hygiene mechanisms.

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

Do not duplicate or independently edit canonical skill content in discovery
surfaces. Do not copy Google Drive root-control documents into `.ai/`.

## Workspace Publication and Retrieval

When Google Drive publication sources are needed, use the Software Delivery
Control Center root sequence:

```text
00_WORKSPACE_BOOTSTRAP.md
01_WORKSPACE_MANIFEST.yaml
02_WORKSPACE_SOURCE_INDEX.md
03_WORKSPACE_OPERATING_INSTRUCTIONS.md
04_WORKSPACE_CURRENT_STATE.md
```

`04_WORKSPACE_CURRENT_STATE.md` is a publication-state summary, not repository
truth.

The Drive publication hierarchy is:

```text
Tier 0 — one root router
Tier 1 — 11 numbered collection indexes
Tier 2 — 36 lifecycle, subtype, Governance, Template, and System indexes
Tier 3 — package-, goal-, and archive-local indexes
```

Load only the smallest authoritative context required. Every durable Drive
publication has one nearest owning index. Parent indexes must not recursively
duplicate descendants. Archived snapshots and the superseded legacy index are
not current-state shortcuts. Duplicate titles do not establish identity; use
Drive IDs and logical paths.

## Goal-Control Model

A governed goal uses:

1. a durable goal charter;
2. an explicit lifecycle state;
3. an operator-issued authorization bound to repository identity;
4. one selected workflow skill;
5. required artifacts and evidence;
6. a checkpoint that terminates the invocation;
7. independent review;
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
→ Merge Readiness
→ Explicit Merge Authorization
→ Post-Merge Validation
→ Branch and Worktree Cleanup, Retention, or Blocker Receipt
→ Bounded Closure or Separately Authorized Readiness Assessment
```

Stages may repeat only through explicit, traceable authorization. Merge,
cleanup, deployment, production activation, and risk acceptance are separate
transitions.

## Repository Test Selection

Use `.ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md` for
repository-specific validation scope and failure disposition.

Test selection must be proportional to the changed risk surface. Every failure
must be classified using evidence. A separately authorized corrective stream
must use isolated branch/worktree ownership and must not overlap the primary
stream. Merge readiness requires zero unresolved failures in applicable
required-safe suites.

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

## Durable Publication Registration

A durable Drive publication must, when applicable, record:

- title;
- primary classification;
- artifact type;
- status;
- version;
- Drive ID;
- logical path;
- purpose;
- representation;
- canonical repository or GitHub pointer.

Revise a publication in place when continuity is intended and preserve its
Drive ID. Register it in the nearest owning index. Publication success or
failure does not mutate canonical engineering state and does not imply
approval, merge, deployment, production readiness, or authorization.

## Native Document Representation

`NATIVE-DOCUMENT-REPRESENTATION-CONTROL.md`, control
`WSP-REPRESENTATION-CONTROL-001`, governs native Google Docs.

A native Google Doc has a stable Drive identity and revision history but no
portable raw-byte SHA-256. Integrity claims must identify the representation
and use one hash scope:

```text
stored_raw_bytes
source_bytes
exported_bytes
not_applicable
```

Hashes from different representation classes are not interchangeable. Never
imply that a native Google Doc is byte-identical to a Markdown, YAML, JSON, or
Office source without separately verified source-byte evidence.

## Evidence and Trust

- Agent summaries are not proof.
- Evidence must correspond to the reported repository SHA and environment.
- Independent review must identify the exact reviewed SHA.
- Evidence entries must identify representation and hash scope when material.
- Preserve commands, exit codes, outputs, metrics, hashes, and limitations.
- Failed and invalid attempts remain part of the engineering record.
- A publication receipt proves publication activity, not technical correctness.
- Merge, cleanup, deployment, production, and operational readiness are
  separate decisions.
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
→ Merge Readiness
→ Explicit Merge Authorization
→ Post-Merge Validation
→ Branch and Worktree Closeout
→ Deployment Readiness
→ Production Readiness
→ Go/No-Go
→ Explicitly Authorized Deploy
```
