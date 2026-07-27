# AEOS Skill Operating Contract

Apply this contract whenever any canonical AEOS skill is used.

## Governing-source preflight

Read in repository-defined order:

1. `CLAUDE.md` or the active harness adapter;
2. `AGENTS.md`;
3. `AI_OPERATING_MANUAL.md`;
4. `.ai/project-sources/00_AEOS_MASTER_INDEX.md`;
5. governing AEOS sources selected by the Master Index;
6. repository-local ADRs and policies;
7. approved goal, plan, review, evidence, and authorization artifacts for the
   current state.

For this repository, include ADR-019, `POL-GIT-HYGIENE-001`, and the repository
test-selection standard when applicable. Report conflicts and stop rather than
silently choosing a weaker source.

## Truth precedence

1. Authenticated runtime evidence for deployed behavior.
2. Authenticated repository and GitHub state for engineering identity.
3. Repository-local governance, approved specifications, and criteria.
4. AEOS governance.
5. Approved publication/reference governance for publication matters.
6. Prior conversations and agent reports as claims.
7. Model memory or general knowledge.

## Action authority

The current operator instruction defines task intent and permitted action scope.
It does not alter facts or approve an unstated action.

Only the operator may authorize state transitions, merge, cleanup, deployment,
production activation, destructive action, or risk acceptance. Access,
publication, prior approval, and tool capability do not grant authority.

## Mandatory pre-edit record

Before editing, report and record:

- repository path and authenticated remote;
- default branch;
- registered branch and worktree identities;
- branch, worktree path, base SHA, exact head SHA, and upstream;
- pull request and required checks when applicable;
- dirty and untracked state;
- active goal, state, work item, and checkpoint;
- authorization identifier and authorized action/transition;
- permitted scope and prohibited actions.

A non-canonical branch or worktree must be registered before substantive work.

## Exact-identity binding

Authorization, review, audit, tests, and evidence must identify the exact
repository or artifact identity to which they apply. Repository drift or a
later commit invalidates current-head approval and identity-bound authorization
unless explicitly reauthorized.

## Universal prohibitions without explicit operator authorization

Do not:

- push, merge, force-push, rebase shared history, or rewrite history;
- reset hard or run broad destructive clean;
- remove worktrees or delete local/remote branches;
- prune worktree metadata or remote references;
- delete data, evidence, tags, or refs;
- deploy or activate production services;
- modify credentials, secrets, or authentication policy;
- run irreversible migrations;
- weaken tests, thresholds, evidence requirements, or safeguards;
- accept risk;
- approve work produced by the same execution context as independent review;
- modify closed checkpoint evidence;
- activate the next workflow state.

Worktree removal, local branch deletion, remote branch deletion, worktree
metadata pruning, and remote-reference pruning are separate actions.

## Preservation-before-cleanup rules

Before cleanup, deletion, or pruning:

1. inventory relevant branches, worktrees, refs, tags, dirty state, locks, and
   process dependencies;
2. perform no-prune fetch when remote state matters;
3. preserve unique, dirty, inaccessible, uncertain, or process-dependent state;
4. prove integration, patch equivalence, retention need, or blocker;
5. preview the exact target action;
6. obtain target-specific authorization.

Uncertainty fails closed to preservation.

## Evidence rules

- Agent narrative is not proof.
- Preserve exact commands, timestamps, exit codes, outputs, and failed attempts.
- Bind evidence to exact repository and environment identity.
- Record representation, MIME type, hash scope, and SHA-256 when material.
- Valid hash scopes are `stored_raw_bytes`, `source_bytes`, `exported_bytes`,
  and `not_applicable`.
- Hashes from different representation classes are not interchangeable.
- Distinguish `VERIFIED`, `CLAIMED_NOT_VERIFIED`, `ASSUMED`, `UNKNOWN`,
  `UNAVAILABLE`, and `NOT_APPLICABLE`.
- Disclose material access limitations.
- A publication receipt proves publication, not correctness or authorization.
- Never claim a readiness category not explicitly evaluated.

## Merge and closeout rules

Merge transitions the goal or work item to `MERGED_PENDING_CLEANUP`, not
`CLOSED`.

Closure requires:

- accepted merge identity;
- post-merge validation or explicit not-required decision;
- preservation and integration evidence;
- worktree/local branch/remote branch/metadata/ref disposition;
- cleanup, retention, or blocker receipt;
- operator-authorized closure transition.

## Stop rules

Stop immediately when:

- authorization is absent, expired, mismatched, or exceeded;
- repository drift invalidates authorization or review;
- required governance is missing or contradictory;
- scope or architecture must change;
- a consequential action is required;
- acceptance criteria are ambiguous;
- evidence cannot support the requested claim;
- retry limits are exhausted;
- the environment is invalid;
- sensitive information may be exposed;
- required-safe-suite failures remain unresolved;
- cleanup inventory, preservation, proof, or authority is incomplete.

## Required terminal dispositions

Use one bounded disposition appropriate to the active workflow:

- `READY_FOR_EXTERNAL_REVIEW`
- `IMPLEMENTATION_COMPLETE_PENDING_AUDIT`
- `CORRECTIVE_WORK_READY_FOR_REAUDIT`
- `READY_FOR_MERGE_REVIEW`
- `MERGED_PENDING_CLEANUP`
- `POST_MERGE_VALIDATION_COMPLETE`
- `CLOSEOUT_READY_FOR_OPERATOR_DECISION`
- `BLOCKED`
- `INSUFFICIENT_EVIDENCE`
- `ENVIRONMENT_INVALID`
- `FAILED_BOUNDED`
- `OPERATOR_AUTHORIZATION_REQUIRED`

Never emit `GO`, `APPROVED`, `CLOSED`, or `PRODUCTION_READY` unless the active
independent decision workflow and evidence support that exact bounded decision.
