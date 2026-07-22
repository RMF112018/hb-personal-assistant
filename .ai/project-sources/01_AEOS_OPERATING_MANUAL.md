---
standard: AEOS
version: "1.1"
status: normative
license: internal-use
---

# 01 — AEOS Operating Manual

## 1. Purpose

This manual governs the planning, review, implementation-control, evidence, and
assurance layer used in AI-assisted software delivery. It makes work repeatable,
auditable, and safe without replacing engineering judgment.

## 2. Core Principles

1. **Repository truth before design.** Verify material repository and GitHub
   claims before relying on them.
2. **Runtime truth for deployed behavior.** Plans and code inspection do not
   establish actual runtime behavior.
3. **Evidence before trust.** Confidence, narrative quality, and agent reports
   are not proof.
4. **Human authority over consequential action.** Models may recommend but may
   not self-authorize.
5. **Independent verification.** Consequential implementation and review use
   separate contexts.
6. **Fail closed.** Missing, stale, ambiguous, or conflicting evidence reduces
   the allowable confidence.
7. **Scope preservation.** Changes to objective, architecture, constraints, or
   acceptance criteria require explicit disposition.
8. **Artifact-centric continuity.** Durable state belongs in governed
   repository, evidence, decision, and publication artifacts.

## 3. Truth Precedence

When factual sources conflict:

1. authenticated runtime evidence for deployed behavior;
2. authenticated repository and GitHub state for engineering identity and
   lifecycle;
3. repository-local governance, accepted ADRs, approved specifications, and
   acceptance criteria;
4. AEOS standards;
5. approved publication/reference governance for publication matters;
6. prior conversations and agent reports as claim indexes;
7. model memory or general knowledge.

A lower-authority source SHALL NOT override a higher-authority source.

## 4. Action Authority

The current operator instruction defines task intent and permitted scope. It
does not change factual evidence or approve an unstated action.

The operator retains final decision, authorization, and risk authority.
Repository access, Workspace access, publication status, prior approval, or
tool capability does not grant action authority.

Without explicit operator authorization, a model SHALL NOT:

- merge or force-push;
- rewrite history;
- delete branches, worktrees, refs, data, or evidence;
- prune worktree metadata or remote references;
- deploy or activate production;
- mutate secrets or credentials;
- run irreversible migrations;
- accept risk;
- approve its own implementation as independent review;
- activate the next governed state.

## 5. GitHub-First Engineering State

Repository content and authenticated GitHub issues, branches, worktrees,
commits, pull requests, reviews, checks, and merge state are canonical for
engineering execution.

Drive and other publication surfaces may publish or reference engineering
identities but SHALL NOT independently define or activate the active goal, work
item, authorization, branch, SHA, PR, review, merge state, or checkpoint.

Repository-specific governance MAY impose stronger controls. For
`RMF112018/hb-personal-assistant`, ADR-019 and `POL-GIT-HYGIENE-001` govern.
Merge transitions work to `MERGED_PENDING_CLEANUP`, not directly to `CLOSED`.

## 6. Required Session Preflight

Before substantive work, identify:

- operating mode;
- repository and authenticated remote;
- issue or goal;
- work item and authorization;
- branch and worktree identities;
- base SHA and exact head SHA;
- pull request and checks;
- review identity and reviewed head, when applicable;
- lifecycle state and checkpoint;
- objective and expected artifact;
- governing sources;
- evidence and access limitations;
- acceptance criteria;
- constraints and stop conditions.

Do not proceed on a material identity assumption when the state can be
authenticated.

## 7. Operating Modes

Use one primary mode unless an end-to-end workflow is explicitly authorized:

- Discovery / Repository Truth
- Architecture
- Goal Engineering
- Implementation Planning
- Plan Review
- Implementation Execution
- Evidence Packaging
- Implementation Audit
- Corrective Review
- Finding Reconciliation
- Merge Readiness
- Post-Merge Validation
- Branch and Worktree Closeout
- Deployment Readiness
- Production Readiness
- Go / No-Go
- Pattern / Corpus Review

Planning, implementation, independent review, merge authorization, cleanup,
deployment, and production decisions SHALL remain distinct.

## 8. Goal and State Discipline

A governed invocation has exactly one active state. The model may execute only
the authorized state and may request but not activate the next state.

Authorization SHALL identify the goal, work item, transition or action,
repository identity, expected branch/worktree, and expected head where
applicable. Repository drift invalidates authorization unless the authorization
explicitly permits the changed identity.

A later commit invalidates current-head review approval.

## 9. Branch and Worktree Discipline

Register every non-canonical branch and worktree before substantive editing.

Inventory, no-prune fetch, preservation, and integration proof SHALL precede
pruning or deletion. Worktree removal, local branch deletion, remote branch
deletion, worktree metadata pruning, and remote-reference pruning are separate
actions.

Closure after merge requires:

- accepted merge identity;
- post-merge validation or explicit not-required decision;
- preservation/disposition of dirty and untracked material;
- integration or retention proof;
- worktree, local branch, and remote branch disposition;
- cleanup, retention, or blocker receipt.

## 10. Evidence and Trust

Evidence SHALL be specific, relevant, reproducible, current, and bound to the
claim it supports.

Record as applicable:

- repository, branch, worktree, base SHA, and exact head SHA;
- environment and runtime identity;
- commands, exit codes, outputs, and timestamps;
- tests and failure classifications;
- artifact representation, MIME type, hash scope, and SHA-256;
- limitations, redactions, and unavailable evidence.

Valid hash scopes are:

- `stored_raw_bytes`
- `source_bytes`
- `exported_bytes`
- `not_applicable`

Hashes from different representation classes are not interchangeable. A native
Google Doc has stable object identity and revision history but no portable
raw-byte SHA-256.

## 11. Durable Artifacts and Publication

Repository engineering artifacts remain canonical in the repository and
GitHub. Publication artifacts may provide collaboration and external handoff.

A durable publication SHOULD record:

- title;
- classification and artifact type;
- status and version;
- stable publication identity and logical path;
- purpose;
- representation and hash scope;
- canonical repository or GitHub pointer.

Publication does not imply approval, implementation, audit passage, merge
readiness, deployment readiness, production readiness, or authorization.

## 12. Reviews and Decisions

A plan or architecture review may conclude:

- `APPROVE`
- `APPROVE WITH REQUIRED CHANGES`
- `REVISE`
- `REJECT`
- `INSUFFICIENT EVIDENCE`

An implementation audit may conclude:

- `PASS`
- `PASS WITH NON-BLOCKING FINDINGS`
- `FAIL — BLOCKERS REMAIN`
- `INSUFFICIENT EVIDENCE`

Readiness decisions are separately scoped and may conclude:

- `GO`
- `CONDITIONAL GO`
- `NO-GO`
- `INSUFFICIENT EVIDENCE`

Every disposition SHALL identify exact scope, identity, evidence basis,
blockers, conditions, and residual risk.

## 13. Conformance

A conforming session:

- authenticates material identity;
- distinguishes truth from authorization;
- separates verified facts from claims and assumptions;
- binds evidence and review to exact identities;
- preserves scope and unresolved findings;
- uses proportional tests and classifies failures;
- stops at authorization boundaries;
- preserves state when evidence or authority is insufficient;
- produces or explicitly defers required durable artifacts.

## 14. Related Standards

- `02_AEOS_WORKFLOW_STANDARD.md`
- `03_AEOS_ARTIFACT_STANDARD.md`
- `04_AEOS_EVIDENCE_AND_TRUST_STANDARD.md`
- `05_AEOS_REVIEW_AND_AUDIT_STANDARD.md`
- `06_AEOS_PRODUCTION_READINESS_STANDARD.md`
- `07_AEOS_LOCAL_AGENT_OPERATING_CONTRACT.md`
- `08_AEOS_VOCABULARY_AND_TAXONOMY.md`
- `09_AEOS_PATTERN_LANGUAGE.md`
- `10_AEOS_PROMPT_ENTRY_POINTS.md`
- `11_REPOSITORY_TEST_SELECTION_STANDARD.md`
