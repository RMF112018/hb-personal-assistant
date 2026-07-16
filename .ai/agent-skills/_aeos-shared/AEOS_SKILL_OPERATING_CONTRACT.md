# AEOS Skill Operating Contract

Apply this contract whenever any skill in this package is used.

## Governing-source preflight

Before substantive work, read in repository-defined order:

1. `CLAUDE.md`
2. `AGENTS.md`
3. `AI_OPERATING_MANUAL.md`, when present
4. `.ai/project-sources/00_AEOS_MASTER_INDEX.md`
5. Governing AEOS sources selected by the Master Index
6. Approved goal, architecture, plan, acceptance criteria, review, and authorization artifacts for the current state

If paths differ in the current repository, establish the current authoritative locations from repository truth. Report conflicts and stop rather than silently selecting a weaker source.

## Authority order

1. Current repository and runtime evidence
2. Approved repository-specific specification and acceptance criteria
3. Repository-local ADRs, policies, and instructions
4. AEOS governance
5. Current operator instruction
6. Prior conversation or model memory

## Mandatory pre-edit record

Before any edit, report and record:

- repository path;
- branch;
- HEAD SHA;
- upstream, when available;
- worktree status;
- active goal and state;
- authorization identifier;
- permitted scope;
- prohibited actions.

## Universal prohibitions without explicit operator authorization

Do not:

- push, merge, force-push, or rewrite history;
- reset hard;
- delete branches or worktrees;
- deploy or activate production services;
- modify credentials, secrets, or authentication policy;
- run irreversible migrations;
- weaken tests, thresholds, evidence requirements, or safeguards;
- accept risk;
- approve a plan or implementation created by the same execution context;
- modify closed checkpoint evidence;
- activate the next workflow state.

## Evidence rules

- Do not use agent narrative as proof.
- Preserve exact commands, exit codes, and outputs.
- Distinguish `VERIFIED`, `CLAIMED_NOT_VERIFIED`, `ASSUMED`, `UNKNOWN`, and `UNAVAILABLE`.
- Preserve failed and invalid attempts.
- Reference evidence by stable path and hash.
- Disclose material access limitations.
- Never claim a readiness category not explicitly evaluated.

## Stop rules

Stop immediately when:

- authorization is absent, expired, mismatched, or invalid;
- repository drift invalidates authorization;
- required governance is missing or contradictory;
- scope or architecture must change;
- a consequential action is required;
- acceptance criteria are ambiguous;
- evidence cannot support the requested claim;
- retry or correction limits are exhausted;
- the environment is invalid;
- sensitive information may be exposed.

## Required terminal disposition

Use one bounded disposition:

- `READY_FOR_EXTERNAL_REVIEW`
- `IMPLEMENTATION_COMPLETE_PENDING_AUDIT`
- `CORRECTIVE_WORK_READY_FOR_REAUDIT`
- `BLOCKED`
- `INSUFFICIENT_EVIDENCE`
- `ENVIRONMENT_INVALID`
- `FAILED_BOUNDED`
- `OPERATOR_AUTHORIZATION_REQUIRED`

Never emit `GO`, `APPROVED`, or `PRODUCTION_READY` unless the currently authorized workflow is an independent decision workflow and evidence supports that exact bounded decision.
