---
title: "AEOS Standing Policy and Receipt Control Plane"
artifact_id: "ADR-020"
classification: "ADRs"
artifact_type: "Architectural Decision Record"
version: "0.1"
status: "Proposed — Independent Architecture Review Required"
date_created: "2026-07-22"
date_updated: "2026-07-22"
decision_owner: "Bobby Fetting"
author: "OpenAI ChatGPT, operator-directed"
repository: "RMF112018/hb-personal-assistant"
branch: "arch/adr-020-aeos-governance-automation-r1"
base_sha: "b2b7bb63443bf5a098c2851eb101e4d5c148c589"
planning_artifact_id: "PLAN-AEOS-GOVERNANCE-AUTOMATION-AMENDMENT-001-R6"
planning_artifact_sha256: "0cc105b375f09bb5df712a13488dcaa07375520315f2b1dc708409eaf6421dd6"
qualifying_plan_review_id: "REVIEW-PLAN-AEOS-GOVERNANCE-AUTOMATION-AMENDMENT-R6-20260722-01"
qualifying_plan_review_sha256: "2a6f92adeeb3a7aa947ba1ed6582b998b1e2ae61dafee03770953d5a9d49223b"
repository_truth_report_id: "AUDIT-AEOS-GOVERNANCE-AUTOMATION-WP-GOV-01-REPOSITORY-TRUTH-R1"
repository_truth_report_sha256: "ace76048c940151fca5640bb561d2f6a497824c133a097b57b5e0fb322c6ca5c"
decision_scope: "AEOS review acceptance, standing action policy, trusted context, receipt persistence, policy/pilot lifecycle, configuration recovery, compatibility, and publication topology"
supersedes: []
superseded_by: []
related_artifacts:
  - "ADR-019"
  - "POL-GIT-HYGIENE-001"
  - "PLAN-AEOS-GOVERNANCE-AUTOMATION-AMENDMENT-001-R6"
  - "AUDIT-AEOS-GOVERNANCE-AUTOMATION-WP-GOV-01-REPOSITORY-TRUTH-R1"
tags:
  - aeos
  - governance
  - standing-policy
  - receipts
  - exact-head
  - github-app
  - event-sourcing
  - policy-lifecycle
---

# AEOS Standing Policy and Receipt Control Plane

## 1. Decision status and authority boundary

This record is a **proposed architecture**. It has no action effect until it receives a fresh independent architecture review and a separate operator acceptance decision bound to the exact reviewed repository head.

This record does not authorize implementation, policy activation, GitHub App creation or installation, credential or secret changes, receipt-branch creation, ruleset changes, required-check changes, configuration mutation, pilot execution, merge, cleanup, Drive publication, deployment, production activation, or risk acceptance.

ADR-019 remains controlling for authority precedence: repository and authenticated GitHub state govern engineering execution, runtime evidence governs deployed behavior, Google Drive governs publication identity and history, and the operator retains final authorization and risk authority.

## 2. Context

The approved R6 governance-automation plan establishes a six-layer decision architecture, exact-head review receipts, standing review acceptance, narrowly bounded standing action policies, one-action authorizations, successor prompts, authorized transition handoffs, a closed policy/member/pilot lifecycle, and deterministic recovery.

Repository truth at base `b2b7bb63443bf5a098c2851eb101e4d5c148c589` confirms that the current repository is still the schema-v2 baseline:

- external review combines later operator disposition in `operator_decision`;
- checkpoints hard-code `operator_action_required: true`;
- state and authorization contracts do not model standing policies, context attestations, receipt events, policy members, pilot attempts, or exact configuration successors;
- the current validator has no receipt CAS, policy lifecycle, context, or pilot controller logic;
- the current AEOS governance workflow is read-only;
- no `aeos/receipts` branch or receipt controller exists;
- rulesets, branch protection, required-check configuration, bypass actors, local worktrees, locks, and process use were not directly verifiable.

The architecture must therefore define an enforceable target without treating unavailable settings, absent search results, or existing narrative claims as proof.

## 3. Decision summary

Adopt a repository-hosted, event-sourced AEOS control plane with these properties:

1. **Static definitions on `main`.** Normative standards, schemas, policy source versions, policy-to-pilot mappings, manifests, validators, workflows, and human-readable governance remain ordinary reviewed repository content.
2. **Dynamic evidence on a dedicated receipt branch.** Accepted reviews, acceptance decisions, policy evaluations, authorizations, action starts/results, handoffs, transitions, suspension, recovery, and activation decisions are immutable events on `refs/heads/aeos/receipts`.
3. **One trusted receipt writer.** A dedicated GitHub App installation named conceptually `aeos-receipt-controller` is the only routine writer and the only routine ruleset bypass actor for the receipt branch.
4. **Same-run validation and verification.** The controller validates, appends through expected-parent non-force CAS, reads back, and verifies the event in one workflow run. It does not depend on a receipt-branch push triggering another workflow.
5. **Exact event authority.** Receipt event files plus their Git commit, tree, blob, payload hash, issuer, and context attestation are authoritative. Catalogs and snapshots are derived caches only.
6. **Controller-issued context attestations.** A review or action context is eligible for standing policy only when a trusted attestation provider issues a one-time, exact-scope context record with an immutable log reference.
7. **Separate evaluators.** Technical review validity, review acceptance, action-policy eligibility, authorization, successor prompt, authorized handoff, and transition readiness are calculated and persisted separately.
8. **Version-bound policy members.** Each standing policy ID and version maps to an immutable ordered pilot set. Cohort state never substitutes for exact member state.
9. **One action per authority.** Every consequential action, including configuration apply, planned restoration, failure rollback, merge, post-merge validation, cleanup, publication, and closure, uses a distinct one-use authorization and receipt chain.
10. **Fail-closed recovery.** Ambiguous action consumption, unknown mutation state, receipt-integrity failure, policy drift, exact-head drift, or context failure suspends the affected scope and preserves history.
11. **Compatibility without history rewrite.** Legacy-v1 and historical-v2 records remain readable and unchanged. Active conversion to v3 requires an explicit conversion receipt.
12. **Publication remains non-authorizing.** Drive receives versioned publication copies through nearest owning indexes only after separately authorized merge and post-merge validation.

## 4. Goals and non-goals

### 4.1 Goals

- Remove GitHub green `APPROVED` as a mandatory AEOS technical-review condition while preserving substantive independent exact-head review.
- Permit a qualifying passing AI review to become accepted under an active standing policy.
- Minimize operator involvement for routine, low-risk, fully specified actions without transferring risk authority.
- Ensure every dynamic governance decision is immutable, exact-identity-bound, replay-resistant, and independently evaluable.
- Preserve implementer/reviewer separation, stable findings, failed evidence, and lifecycle history.
- Provide deterministic policy-member, pilot, configuration, recovery, and transition behavior.
- Make receipt concurrency safe without mutating the reviewed candidate.
- Support multiple agent harnesses without allowing adapters to weaken canonical rules.

### 4.2 Non-goals

- Automatic policy activation.
- Automatic production activation, deployment, migration, credential management, legal/compliance judgment, or material risk acceptance.
- Automatic destructive cleanup under uncertainty.
- Treating a model assertion of independence as trusted context evidence.
- Replacing GitHub with Drive or a separate orchestration ledger.
- Rewriting historical v1/v2 records.
- Proving current ruleset, local worktree, credential, or configuration state through architecture prose.

## 5. Architectural invariants

`INV-ADR020-001` — Exactly one AEOS workflow state is active per invocation.

`INV-ADR020-002` — A model may request but cannot activate the next state.

`INV-ADR020-003` — Technical review validity is independent of GitHub native review state and independent of later acceptance or action authority.

`INV-ADR020-004` — Review acceptance is independent of action-policy eligibility.

`INV-ADR020-005` — Action-policy eligibility has no successor-prompt or authorized-handoff dependency.

`INV-ADR020-006` — Authorization precedes authorized transition handoff; a handoff cannot create authority.

`INV-ADR020-007` — One authorization permits one action class, one target, one attempt, and one exact identity set.

`INV-ADR020-008` — Candidate branches are never modified merely to persist review or governance receipts.

`INV-ADR020-009` — Receipt events are append-only, non-force, exact-parent, idempotent, and independently read back.

`INV-ADR020-010` — Catalogs, dashboards, indexes, and materialized state views are derived and cannot satisfy an authoritative receipt reference.

`INV-ADR020-011` — A policy member can act only when that exact ID/version is `ACTIVE`; cohort state alone grants no action effect.

`INV-ADR020-012` — Pilot order and policy coverage come only from immutable versioned mappings and manifests.

`INV-ADR020-013` — A corrective implementer cannot establish its own qualifying blocker or set `VERIFIED_FIXED`.

`INV-ADR020-014` — Planned restoration and failure rollback use different identities, action classes, authorities, receipts, and successors.

`INV-ADR020-015` — Merge, post-merge validation, cleanup, publication, deployment, production activation, and closure remain separate.

`INV-ADR020-016` — Any credential or secret lifecycle action routes to `OP-EXC-006`.

`INV-ADR020-017` — Missing, stale, ambiguous, conflicting, or unavailable material evidence reduces authority and fails closed.

## 6. Six-layer decision architecture

### 6.1 Ordered calculation

The control plane calculates and persists these independent results:

1. `technical_review_validity`
2. `review_acceptance`
3. `action_policy_eligibility`
4. `action_authorization`
5. `handoff_readiness`
6. `transition_readiness`

A later green result cannot overwrite an earlier failure. The aggregate check is a projection of all component results, not an alternative source of truth.

### 6.2 Technical review validity

Technical validity evaluates:

- correct review type;
- trusted independent context;
- exact artifact and repository/head identity;
- qualifying review disposition;
- acceptance-criteria and finding treatment;
- evidence sufficiency and limitations;
- durable formal review receipt;
- platform-state independence;
- conflict, tamper, drift, replay, and supersession;
- trusted policy and evaluator integrity;
- complete non-authorizing successor prompt when nonterminal.

`REV-GATE-008` is not part of technical validity. It is the standing-policy acceptance decision applied only after technical validity passes.

### 6.3 Review acceptance

A review is accepted only when:

- technical validity is `VALID_PASSING`;
- the exact review-acceptance policy member is `ACTIVE`;
- policy eligibility is `ELIGIBLE`;
- no emergency freeze, suspension, drift, or conflict is active;
- the acceptance evaluator appends an exact acceptance event.

A blocking review may become an `ACCEPTED_BLOCKING_DETERMINATION` under the same integrity rules. That acceptance permits only the bounded corrective route defined by policy; it does not make the implementation acceptable.

### 6.4 Action authorization

Standing policy can authorize only an action class explicitly listed in the exact active policy member. Each issued authority binds:

- policy ID/version/hash;
- mapping/cohort/member identity;
- repository, base, head, target, and action class;
- work item and current state;
- attempt and idempotency key;
- qualifying review, findings, and evidence;
- expiry and drift conditions;
- exact prohibited actions.

Authorization issuance and consumption are separate receipt events.

## 7. Static and dynamic record ownership

### 7.1 `main` owns static normative definitions

The following remain reviewed repository files:

```text
docs/decisions/ADR-020-aeos-standing-policy-and-receipt-control-plane.md
docs/governance/aeos-standing-policy-lifecycle.md
docs/governance/aeos-standing-policy-register.yaml
.ai/aeos/policies/standing/<policy-id>/<version>/policy.yaml
.ai/aeos/policies/mappings/<mapping-id>/<version>/mapping.yaml
.ai/aeos/policies/manifests/<manifest-id>/<version>/manifest.yaml
.ai/schemas/goal-loop/*.schema.json
.ai/templates/goal-loop/*
.ai/aeos/bin/*
.ai/agent-skills/*
.github/workflows/aeos-receipt-controller.yml
```

The repository policy source is immutable by version. A semantic policy change creates a new version and a new review/activation lifecycle.

### 7.2 `aeos/receipts` owns dynamic authoritative events

The receipt branch contains only controller-owned branch metadata and immutable event files:

```text
branch-manifest.json
events/YYYY/MM/<event-id>.json
```

The authoritative receipt identity is:

```yaml
receipt_branch: refs/heads/aeos/receipts
receipt_commit_sha:
receipt_tree_sha:
receipt_blob_sha:
event_path:
event_id:
event_payload_sha256:
event_schema_id:
issuer_app_id:
issuer_installation_id:
controller_workflow:
controller_run_id:
context_attestation_id:
```

No candidate branch, PR branch, or `main` commit is modified to record a review or action event.

### 7.3 Derived views

These may be generated from the event chain but are not authoritative:

- receipt catalogs;
- current-state snapshots;
- policy dashboards;
- branch/worktree dashboards;
- search indexes;
- Drive summaries;
- cached aggregate checks.

A validator resolves the exact event path and verifies the commit/blob/payload chain. A catalog pointer alone is insufficient.

## 8. Receipt controller trust architecture

### 8.1 Selected issuer

The routine receipt writer is a dedicated GitHub App installation, conceptually named `aeos-receipt-controller`.

Minimum intended permissions:

| Permission | Level | Purpose |
|---|---|---|
| Metadata | Read | Repository identity |
| Contents | Read/write | Create Git objects and fast-forward `aeos/receipts` |
| Actions | Read | Bind controller run and verify workflow identity |
| Checks | Read | Read candidate checks when evaluating gates |
| Pull requests | Read | Resolve PR/base/head/review metadata |
| Issues | Read | Resolve governed work-item metadata when used |

The App does not receive Administration, Secrets, Environments, Deployments, Actions-write, Pull-requests-write, or Issues-write permission for the receipt function.

Creating or installing the App, storing its private key, changing installation permissions, rotating credentials, or adding secrets is `OP-EXC-006` and requires exact operator authorization.

### 8.2 Why `GITHUB_TOKEN` is not the selected long-term issuer

A workflow can request `contents: write`, but events created with the repository `GITHUB_TOKEN` generally do not trigger another workflow run, except `workflow_dispatch` and `repository_dispatch`. A design that depends on a receipt-branch push starting a second validation workflow is therefore rejected.

The selected controller performs validate → append → readback verification in one run. The dedicated App is selected because it can be a named least-privilege ruleset bypass actor and provides a stable installation identity. The architecture does not require push recursion.

### 8.3 Workflow entry

Permitted entry events are:

- `workflow_call` from accepted AEOS workflows;
- `workflow_dispatch` with schema-validated inputs for operator-directed recovery or pilot use;
- `repository_dispatch` from an approved harness gateway.

Untrusted pull-request code does not execute in a privileged receipt-writing context. `pull_request_target` is prohibited for running candidate-controlled scripts or consuming receipt credentials.

### 8.4 Protection and bootstrap ordering

Receipt capability is bootstrapped in this order, with a separate authorization for every mutating stage:

1. Export current rulesets, branch protection, workflow permissions, App installations, and relevant repository settings.
2. Independently validate the export and calculate the desired-state diff.
3. Create/install the dedicated App and credential only under `OP-EXC-006`.
4. Create `aeos/receipts` with a deterministic root manifest commit.
5. Apply an exact branch ruleset targeting only `refs/heads/aeos/receipts`.
6. Independently validate the ruleset readback.
7. Run a non-action shadow receipt append against synthetic evidence.
8. Run bounded contention, idempotency, replay, and recovery pilots.
9. Only after all infrastructure pilots pass may policy behavioral pilots begin.

The receipt ruleset must:

- prohibit deletion;
- prohibit force push and non-fast-forward update;
- require linear history;
- restrict routine updates to the dedicated App;
- name the App as the sole routine bypass actor;
- exclude repository administrators, generic users, teams, and deploy keys from routine bypass;
- preserve an emergency operator recovery path that is disabled during normal operation and governed by `OP-EXC-004`, `OP-EXC-006`, and `OP-EXC-010`.

Required status checks on candidate branches are configured separately. Receipt-branch protection cannot depend on a check that only runs after the protected write, because that creates a bootstrap/deadlock cycle.

## 9. Receipt event and CAS protocol

### 9.1 Canonical event

Each event is canonical JSON encoded as UTF-8 with:

- lexicographically ordered object keys;
- no insignificant whitespace;
- normalized timestamps in UTC;
- lowercase hexadecimal hashes;
- explicit nulls only where the schema permits;
- no unresolved placeholders.

The event ID is:

```text
sha256(
  schema_id
  + event_type
  + idempotency_scope
  + exact governed identities
  + canonical event body excluding event_id
)
```

An event ID collision with different canonical bytes is an integrity conflict and triggers suspension.

### 9.2 Append algorithm

For one append attempt:

1. Authenticate repository, receipt branch, App installation, workflow/run, and freeze state.
2. Validate the request schema, context attestation, exact head, policy/member state, authorization, and action class.
3. Calculate canonical bytes, `event_id`, event path, and payload hash.
4. Read current receipt tip `T0`.
5. If the event path already exists:
   - identical blob/payload → return `IDEMPOTENT_EXISTING`;
   - different blob/payload → return `RECEIPT_ID_CONFLICT` and suspend.
6. Create one blob and a tree derived from `T0` adding exactly one event path.
7. Create commit `C1` with sole parent `T0`.
8. Update `refs/heads/aeos/receipts` to `C1` with `force: false`.
9. On non-fast-forward or validation conflict:
   - preserve attempted parent, commit, request, and controller-run evidence;
   - re-read the branch;
   - resolve idempotency;
   - retry at most five total attempts.
10. After an accepted update:
    - read the ref;
    - read `C1`, its tree, event blob, and event bytes;
    - verify parent `T0`, path, blob SHA, payload hash, issuer, and context;
    - if a later append already advanced the branch, verify `C1` is an ancestor and that the event path at the current tip resolves to the same blob.
11. Emit a component check and workflow artifact containing the complete append evidence.

No force update, reset, rebase, fallback row, first-match routing, or lost-update overwrite is permitted.

### 9.3 Bounded contention outcome

After five unsuccessful attempts:

```text
receipt_append = BLOCKED_CONTENTION
authorization_consumption = NOT_CONSUMED unless a verified consumption event exists
action_effect = PROHIBITED
next_state = SUSPENDED or current safe inactive state
```

The controller must not infer whether an event was written. It resolves the exact path and payload before deciding.

### 9.4 Authorization consumption and action start

Cross-system action execution uses a receipt-first reservation protocol:

1. append `AUTHORIZATION_CONSUMPTION_RESERVED`;
2. verify the reservation readback;
3. permit exactly one adapter invocation;
4. append `ACTION_STARTED` with provider request identity when the provider accepts the action;
5. append `ACTION_RESULT` and independent validation events.

A reservation is terminal for that authorization. If no action starts and direct zero-effect evidence exists, a new authorization may be requested. Ambiguous provider acceptance suspends the scope; the old authorization is never reused.

## 10. Receipt integrity, audit, and recovery

### 10.1 Continuous integrity

A read-only integrity job verifies:

- branch existence;
- non-rewritten ancestry from the deterministic root;
- one-parent linear commits;
- allowed paths only;
- one authoritative event addition per event commit;
- valid event schemas and payload hashes;
- App issuer identity for routine commits;
- exact previous-tip linkage;
- no duplicate/conflicting event IDs;
- deterministic state fold and catalog rebuild.

### 10.2 Emergency freeze

A logical freeze is an authoritative `EMERGENCY_FREEZE_ACTIVATED` event. Every evaluator and controller checks the latest valid freeze state before issuing or consuming authority.

Freeze permits:

- read-only truth collection;
- integrity verification;
- evidence preservation;
- operator-directed reconciliation planning.

Freeze prohibits:

- review-acceptance effect;
- policy eligibility;
- authorization issuance or consumption;
- handoff consumption;
- pilot actions;
- recovery actions;
- activation;
- automatic state transitions.

If the receipt branch or controller is compromised or unavailable, a hard freeze disables the App installation, removes its bypass, or disables the workflow under separately authorized operator exception. Hard freeze is not standing authority.

### 10.3 Recovery

Branch deletion, non-fast-forward rewrite, invalid issuer commits, or integrity failure results in `RECEIPT_INTEGRITY_SUSPENDED`.

Recovery requires:

- exact incident identity;
- verified last-good root/tip and event bundle;
- read-only reconstruction;
- independent assessment;
- operator-authorized restoration;
- no erasure of the compromised chain;
- new recovery receipt linking the restored branch to preserved incident evidence.

No model or controller may force-rewrite the branch as routine recovery.

## 11. Trusted context attestation

### 11.1 Attestation record

A context attestation contains:

```yaml
context_attestation_id:
attestation_version:
issuer_id:
issuer_type:
harness_type:
provider_session_or_run_id:
actor_identity:
role: author | reviewer | controller | operator
repository:
base_sha:
head_sha:
artifact_ids_and_hashes:
authorized_action_class:
one_time_nonce:
issued_at:
expires_at:
immutable_action_log_reference:
parent_context_id:
separation_constraints:
risk_tier:
attestation_status:
```

The issuer, not the model, creates the context ID and nonce. The attestation is exact-head, exact-action, time-bounded, one-use where consequential, and replay checked.

### 11.2 Provider tiers

| Tier | Evidence | Standing-policy eligibility |
|---|---|---|
| `ATTESTED_A` | GitHub Actions/App run identity, exact workflow/ref/SHA, actor, immutable run log, nonce | Eligible when other gates pass |
| `ATTESTED_B` | Approved local/harness gateway issues nonce, records session identity, hashes action log, verifies repository/head and role separation | Eligible only for policy/risk tiers that explicitly permit it |
| `DOCUMENTED_C` | Review artifact and model self-assertion without trusted provider attestation | Technically reviewable, but not eligible for automatic standing-policy acceptance |
| `UNAVAILABLE` | Missing or conflicting issuer/log/separation evidence | Fails closed |

A future provider adapter must map native platform evidence to this canonical record. Adapters cannot upgrade their own evidence tier.

### 11.3 Author/reviewer separation

The reviewer attestation must prove that its context ID, nonce, provider run/session, action log, and role differ from the authoring context. Shared account identity alone does not disqualify a review, but the trusted issuer must establish separate execution contexts and no write action by the reviewer.

For high-risk actions, `ATTESTED_A` or a separately accepted provider-specific contract is required.

## 12. Review receipt and acceptance architecture

### 12.1 Review receipt

A review receipt references:

- review artifact bytes and hash;
- reviewed repository/base/head;
- reviewed files/artifacts;
- context attestation;
- criteria matrix;
- evidence register;
- stable findings and closure tests;
- limitations;
- technical disposition;
- platform review metadata;
- stale-on-drift rules;
- successor prompt hash.

GitHub review state (`COMMENTED`, `APPROVED`, `CHANGES_REQUESTED`) is metadata only.

### 12.2 Dispositions

Plan/architecture:

```text
APPROVE
APPROVE_WITH_REQUIRED_CHANGES
REVISE
REJECT
INSUFFICIENT_EVIDENCE
```

Implementation/corrective:

```text
PASS
PASS_WITH_NON_BLOCKING_FINDINGS
CORRECTIVE_WORK_REQUIRED
BLOCKED
INSUFFICIENT_EVIDENCE
```

Readiness:

```text
GO
CONDITIONAL_GO
NO_GO
INSUFFICIENT_EVIDENCE
```

Legacy values are normalized through explicit compatibility mapping without rewriting historical source.

### 12.3 Acceptance results

```text
ACCEPTED_BY_STANDING_POLICY
ACCEPTED_BLOCKING_DETERMINATION
CONDITIONAL_PENDING_VERIFICATION
NOT_ACCEPTED
INELIGIBLE
SUSPENDED
```

Acceptance never issues implementation, merge, cleanup, publication, deployment, or production authority.

## 13. Standing policy source and lifecycle

### 13.1 Initial policy family

The initial source versions are:

- `POL-AEOS-AUTO-ACCEPT-001` `1.0.0`
- `POL-AEOS-STANDING-IMPLEMENT-001` `1.0.0`
- `POL-AEOS-STANDING-CORRECTIVE-001` `1.0.0`
- `POL-AEOS-STANDING-REVIEW-ROUTE-001` `1.0.0`
- `POL-AEOS-STANDING-MERGE-001` `1.0.0`
- `POL-AEOS-STANDING-POST-MERGE-001` `1.0.0`
- `POL-AEOS-STANDING-CLOSEOUT-001` `1.0.0`
- `POL-AEOS-STANDING-PUBLISH-001` `1.0.0`

Each policy defines exact eligible actions, risk tier, exclusions, evidence, expiry, freeze behavior, and operator-exception routes.

### 13.2 Exact initial mapping

`POLICY-PILOT-MAPPING-001` version `1` maps:

| Policy member | Required behavioral pilots |
|---|---|
| Auto-accept | `PILOT-REVIEW-ACCEPTANCE-001` |
| Review route | `PILOT-REVIEW-ROUTE-001` |
| Implementation | `PILOT-IMPLEMENTATION-001` |
| Corrective | `PILOT-CORRECTIVE-001` |
| Merge | `PILOT-MERGE-001` |
| Post-merge | `PILOT-POST-MERGE-VALIDATION-001` |
| Closeout | `PILOT-SAFE-CLEANUP-001` then `PILOT-CLOSURE-ASSESSMENT-001` |
| Publication | `PILOT-PUBLICATION-001` |

Every member also requires the cohort-wide infrastructure prerequisites defined by the R6 plan. Missing, duplicate, stale, wildcard, range-based, prose-only, or reordered mappings fail closed.

### 13.3 State ownership

Policy source version is static on `main`. Policy member and cohort state are derived from authoritative receipt events.

Closed cohort states:

```text
PROPOSED
INDEPENDENTLY_REVIEWED
OPERATOR_ACCEPTED_INACTIVE
SHADOW_AUTHORIZED
SHADOW_RUNNING
SHADOW_ASSESSMENT
PILOT_SEQUENCE_READY
PILOT_AUTHORIZED
PILOT_RUNNING
PILOT_ASSESSMENT
PILOT_SEQUENCE_COMPLETE
ACTIVATION_ASSESSMENT
ACTIVATION_RECORDED
ROLLBACK_REQUIRED
ROLLBACK_AUTHORIZED
ROLLBACK_RUNNING
ROLLBACK_ASSESSMENT
SUSPENDED
RECONCILIATION_REQUIRED
RESUME_AUTHORIZED
REVOKED
EXPIRED
```

Closed member states:

```text
PROPOSED
INDEPENDENTLY_REVIEWED
OPERATOR_ACCEPTED_INACTIVE
PILOT_EVALUATION_PENDING
ACTIVATION_ELIGIBLE
ACTIVE
SUSPENDED
RECONCILIATION_REQUIRED
RESUME_AUTHORIZED
REVOKED
EXPIRED
```

Only the exact member `ACTIVE` state may provide policy effect.

### 13.4 Lifecycle authority

- Review does not activate.
- Operator bootstrap acceptance moves a reviewed policy version to inactive.
- Shadow and every mutating pilot require separate one-use authority.
- Pilot PASS creates evidence, not activation.
- Independent activation assessment calculates the exact eligible-member set.
- Operator activation names the exact subset.
- A member-local failure does not disable another member unless independent evidence establishes a shared effect.
- Resume never revives old authorizations.
- Revocation is prospective and preserves all history.
- Expiry blocks new effects and requires a new version/cohort for renewal.

## 14. Pilot controller

### 14.1 Manifest separation

The controller owns two immutable ordered manifests:

- infrastructure prerequisites;
- policy behavioral pilots.

The controller exposes only the current exact pilot and attempt. It cannot skip, repeat, reorder, infer, or substitute a pilot.

### 14.2 Authorization rules

A pilot authorization binds:

- sequence and manifest hash;
- current pilot/index;
- policy member where applicable;
- attempt ID;
- repository/head;
- target;
- action class;
- expected evidence;
- exact successor rules.

Consumed, expired, invalidated, suspended, or dependency-failed authority cannot be reused.

### 14.3 Corrective prerequisite

`PILOT-CORRECTIVE-001` is eligible only with an independently produced exact-head blocking review/audit receipt containing stable finding IDs and closure tests.

No qualifying blocker produces:

```text
pilot_outcome = NOT_APPLICABLE
authorization_disposition = NOT_APPLICABLE
authorization_issued = false
member_state = OPERATOR_ACCEPTED_INACTIVE
activation_coverage = false
```

The corrective implementer cannot author the qualifying blocker or set `VERIFIED_FIXED`.

## 15. Configuration adapter and recovery architecture

### 15.1 Canonical adapter interface

A configuration provider adapter must expose separate operations:

```text
export_current_state()
assess_feasibility()
calculate_exact_diff()
apply_exact_change()
validate_forward_state()
restore_planned_before_state()
validate_restored_state()
rollback_failed_change()
assess_rollback()
```

Read methods cannot mutate. Every mutating method receives a distinct authorization class and idempotency key.

### 15.2 Safe pilot target

The first configuration pilot must target a disposable, uniquely named branch/ruleset scope that does not include `main`, release branches, production environments, secrets, deployments, or existing user work.

The preflight must verify:

- exact target;
- before-state raw export and representation hash;
- current ruleset/protection/workflow-permission state;
- provider API capability;
- expected desired state;
- recovery target;
- delete/restore semantics;
- no overlap with unrelated rules.

No disposable target proof means `INFEASIBLE`.

### 15.3 WP-GOV-24B exact routing

After forward apply authority is consumed, terminal outcomes are limited to:

```text
PASS
FAIL
BLOCKED
INSUFFICIENT_EVIDENCE
```

Permitted direct evidence classes are:

```text
RETAINED_STATE_VERIFIED
TEMPORARY_STATE_VERIFIED
ZERO_EFFECT_PROVEN
MUTATION_CONFIRMED_RECOVERY_KNOWN
MUTATION_CONFIRMED_RECOVERY_UNKNOWN_OR_UNSAFE
MUTATION_OR_CONSUMPTION_AMBIGUOUS
```

Every valid `(preflight_mode, outcome, evidence_class)` tuple resolves to exactly one normative row and one successor.

- zero row or zero successor → `CONFIG_SUCCESSOR_MISSING`;
- multiple rows or multiple successors → `CONFIG_SUCCESSOR_AMBIGUOUS`;
- `UNDECIDED`, `INELIGIBLE`, and `NOT_APPLICABLE` are invalid after apply consumption;
- `BLOCKED` never continues the normal sequence;
- no row may enter both planned restoration and failure rollback.

### 15.4 Restoration and rollback

Planned temporary restoration is the named `WP-GOV-24C` pilot followed by independent `WP-GOV-24D` validation.

Failure rollback is outside the pilot manifest and uses:

```text
action_class = CONFIG_FAILURE_ROLLBACK
recovery_id != pilot_id
authorization_id != forward_or_restore_authorization
attempt_id != forward_or_restore_attempt
receipt_id != forward_or_restore_receipt
```

Successful failure rollback returns the cohort inactive and terminalizes the sequence as `ABORTED_ROLLED_BACK`. It cannot resume or advance the existing sequence.

Ambiguous mutation or unsafe/unknown recovery enters `SUSPENDED`.

## 16. Schema v3 and compatibility

### 16.1 V3 contracts

Implementation must create or revise the R6-listed v3 schemas, including:

- review receipt, validity, and acceptance;
- policy evaluation and activation;
- authorization blueprint, binding, authorization, and consumption;
- successor prompt, authorized handoff, and transition readiness;
- context attestation;
- policy mapping and member/cohort state;
- infrastructure/behavioral manifests and pilot attempts;
- configuration plan, validation, and recovery;
- corrective eligibility;
- receipt append event and derived catalog;
- checkpoint/state separation.

Schemas are closed (`additionalProperties: false`) where practical, use explicit enums, reject unresolved placeholders in issued records, and bind exact identities.

### 16.2 Authoritative head validation

The current ineffective self-comparison is replaced conceptually by:

```text
authorization.authorized_identity.repository_head
==
authenticated_execution.repository_head
==
state.repository.head_sha
```

The validator must reject any mismatch and include a mutation-negative fixture that changes only one side.

### 16.3 Compatibility

- Legacy-v1 remains read-only under its existing hash registry.
- Historical v2 remains byte-preserved and readable.
- New active contracts use v3 only after accepted migration.
- Active v2 records convert only through explicit conversion receipts.
- Conversion records source blob/hash, destination blob/hash, semantic mapping, defaults/omissions, exact head, validator result, context, and preservation proof.
- Conversion never activates the converted record.

## 17. Machine checks and ordering

The required component checks are those listed in R6, with `aeos/governance-aggregate` reporting all components.

Execution order is:

```text
static schema/template/parity validation
→ technical review validity
→ review acceptance
→ action-policy eligibility
→ authorization binding/issuance
→ successor prompt integrity
→ authorized handoff integrity
→ transition readiness
→ receipt append/readback integrity
→ resulting state projection
```

For an action:

```text
eligibility PASS
→ authorization ISSUED
→ reservation receipt appended and verified
→ authorized handoff compiled
→ transition readiness PASS
→ action adapter invocation
→ action/result receipts
→ independent validation
→ exact successor evaluation
```

No check can infer a missing earlier result. The aggregate check cannot mask unavailable or red components.

## 18. Ruleset and required-check architecture

### 18.1 Desired-state records

Ruleset/configuration changes use versioned desired-state JSON that records:

- exact repository and target selector;
- current raw export hash;
- desired raw representation;
- semantic diff;
- bypass actors by stable GitHub identity;
- required checks by exact name/source;
- enforcement mode;
- rollback representation;
- unrelated-rule preservation;
- operator authorization;
- readback validation.

### 18.2 Preflight and mutation boundary

No ruleset or branch-protection mutation occurs without:

1. direct authenticated export;
2. independent feasibility and diff review;
3. exact action authorization;
4. one mutation;
5. independent readback validation;
6. separately authorized restoration/rollback if needed.

Unavailable ruleset truth blocks mutation but does not block this ADR.

### 18.3 Candidate required checks

Candidate branches may later require `aeos/governance-aggregate` plus applicable repository gates. Receipt persistence must not require GitHub native green `APPROVED`.

Check names, app sources, bypass semantics, and branch selectors must be exported and validated before configuration pilot authorization.

## 19. Prior branch/worktree reconciliation

Existing registrations and historical evidence are imported as claims, not upgraded conclusions.

Rules:

- current remote tips come from authenticated GitHub;
- current local branches/worktrees/dirty state/locks/processes require local Git evidence;
- absent remote search results are not deletion proof;
- a registration that remains `REVIEW_PENDING` without closeout evidence remains unresolved;
- uncertain, inaccessible, dirty, unique, locked, or process-used entities fail closed to preservation;
- no cleanup action is inferred or authorized by reconciliation;
- each entity receives `VERIFIED_CURRENT`, `RETAINED`, `CLEANUP_BLOCKED`, or another policy-defined evidence classification only after its required evidence is available.

PR #323 branch/worktree closeout remains unresolved until a dedicated read-only inventory and a separately authorized closeout workflow produce the required receipt.

## 20. Operator exceptions

The controller routes these classes without broadening them:

- `OP-EXC-001` unresolved business intent;
- `OP-EXC-002` material architecture choice;
- `OP-EXC-003` material residual risk;
- `OP-EXC-004` irreversible, forceful, broad, unique-work-destructive, or unsupported destructive action;
- `OP-EXC-005` deployment, production activation, or material production change;
- `OP-EXC-006` credential or secret lifecycle action;
- `OP-EXC-007` legal, contractual, privacy, regulatory, or compliance judgment;
- `OP-EXC-008` irreconcilable authoritative evidence conflict;
- `OP-EXC-009` policy gap or ineligible action;
- `OP-EXC-010` emergency suspension, override, or resume decision.

An exception request names one exact decision, evidence, alternatives, consequence, expiry, and allowed answer set. Silence does not authorize.

## 21. Successor prompt and authorized handoff

A nonterminal completion produces a complete successor prompt before authority exists. It is non-authorizing and may state `AUTHORIZATION_REQUIRED`.

After an authorization is issued, the controller compiles a separate authorized transition handoff that references:

- the prompt hash;
- exact authorization receipt;
- current repository/head;
- state/work item/action;
- target and attempt;
- expiry/drift rules;
- prohibited actions.

Transition readiness requires both the active authorization and the matching handoff. Prompt validity is not an eligibility prerequisite.

Terminal output explicitly records no next state/action/authorization/handoff.

## 22. Drive publication topology

### 22.1 Selected policy package owner

When publication is separately authorized after merge and post-merge validation, create:

```text
10-Governance/
  AEOS_Governance_Documents_v1.0/   # existing folder ID 1yNypI2P-qSgDQ4yDLUDn-fL9Gm-zrXEJ
    policies/                       # new package-local folder
      00_AEOS_STANDING_POLICY_INDEX.md
      <versioned policy publications>
```

The existing Tier 2 package index registers only the new direct `policies/` child. The policy index owns its direct policy publications. Parent indexes do not enumerate package internals.

### 22.2 Representation

- Repository-authored Markdown/YAML/JSON publication copies use `source_bytes` when exact source bytes are preserved.
- Native Google Docs use `not_applicable` unless a separately identified source or export is hashed.
- The combined manual v1.0 is preserved; v2.0 is created as a new version.
- Standard 11 and optional `CLAUDE.md` are create operations only if still absent and still required.
- ADR-020 publishes through the verified ADR folder/index.
- R6 plan/review, implementation evidence, pilots, decisions, and receipts publish through their nearest lifecycle/type indexes.

Drive publication cannot activate policy or change repository state.

## 23. Migration and activation sequence

1. Accept ADR-020 through independent exact-head review and operator decision.
2. Rebaseline implementation planning against the accepted ADR head.
3. Implement static v3 schemas, validators, policies, mappings, manifests, and compatibility.
4. Implement receipt controller code without enabling write credentials.
5. Independently audit implementation at exact head.
6. Obtain merge readiness and exact merge authorization.
7. Perform post-merge validation.
8. Export current GitHub configuration.
9. Obtain operator exception for App/credential lifecycle.
10. Bootstrap and protect the receipt branch through separately authorized actions.
11. Run shadow evaluation with zero action effect.
12. Run infrastructure pilots, including configuration preflight/apply/validation/restoration as applicable.
13. Run each behavioral pilot under separate authority.
14. Independently assess eligible policy members.
15. Obtain exact operator activation for an explicit subset.
16. Publish Drive copies under separate publication authorizations.
17. Close only after post-merge validation and branch/worktree disposition receipts.

No stage grants blanket authority for later stages.

## 24. Alternatives considered

### 24.1 Store receipts on the candidate branch

Rejected because every receipt changes the reviewed head and invalidates exact-head review.

### 24.2 Store authoritative receipts only in Drive

Rejected because Drive is publication/reference, lacks repository-native CAS, and would become a competing execution ledger.

### 24.3 Use GitHub PR comments or reviews as the only receipt

Rejected because comments are editable/deletable, platform review state conflates metadata and technical evidence, and exact schema/CAS semantics are weak.

### 24.4 Use `GITHUB_TOKEN` plus a push-triggered second workflow

Rejected because workflow-created events using `GITHUB_TOKEN` generally do not trigger another workflow run. Same-run verification avoids recursion; a dedicated App provides a stable least-privilege bypass identity.

### 24.5 PR-mediated receipt append

Rejected for routine receipts because PR latency and merge authority would couple evidence persistence to a separate review/merge lifecycle. It remains an emergency/manual recovery option only under exact authority.

### 24.6 Mutable database or external service as canonical state

Rejected for the initial architecture because it creates another control plane and weakens repository-native identity. External services may provide attestation or search, but authoritative events remain Git/GitHub receipts.

### 24.7 One policy state for the whole cohort

Rejected because cohort activation would incorrectly grant every member authority and make partial activation/failure nondeterministic.

### 24.8 Automatic activation after pilot PASS

Rejected because policy activation remains an exact operator decision under current governance.

### 24.9 One configuration authorization for apply and rollback

Rejected because it conflates forward intent, planned restoration, failure recovery, and risk.

## 25. Acceptance criteria

| ID | Architecture criterion |
|---|---|
| `AC-GOV-001` | GitHub native review state is metadata and not a technical-review prerequisite. |
| `AC-GOV-002` | Substantive independent review remains mandatory where required. |
| `AC-GOV-003` | Reviews and receipts bind exact artifacts/repository heads without candidate mutation. |
| `AC-GOV-004` | Context evidence is trusted-issuer-created, unique, anti-replay, exact-scope, and risk-tiered. |
| `AC-GOV-005` | Review receipts include criteria, evidence, findings, limitations, disposition, context, and integrity. |
| `AC-GOV-006` | Blocking and insufficient dispositions cannot qualify as passing. |
| `AC-GOV-007` | Review acceptance and action effect require the exact active policy member or explicit authority. |
| `AC-GOV-008` | Validity, acceptance, eligibility, authorization, prompt, handoff, and readiness remain separate. |
| `AC-GOV-009` | Policy eligibility has no prompt/handoff dependency. |
| `AC-GOV-010` | Drift, tamper, replay, contention, conflict, suspension, freeze, and undefined transitions fail closed. |
| `AC-GOV-011` | Implementation authority requires accepted design/plan and concrete exact binding. |
| `AC-GOV-012` | Corrective authority requires independent exact-head stable findings and closure tests. |
| `AC-GOV-013` | Merge requires current exact-head readiness and one-use authority. |
| `AC-GOV-014` | All consequential actions and configuration paths have distinct authorities/receipts and exact successors. |
| `AC-GOV-015` | Drive publication is deterministic, read back, nearest-index registered, and non-authorizing. |
| `AC-GOV-016` | Operator exceptions preserve every enumerated high-consequence and secret boundary. |
| `AC-GOV-017` | Exception questions are narrow, expiring, evidence-bound, and fail closed. |
| `AC-GOV-018` | Every nonterminal consequential completion includes a complete non-authorizing successor prompt. |
| `AC-GOV-019` | Every executable transition has a separate authorization-bound handoff. |
| `AC-GOV-020` | Findings, failed evidence, contention, attempts, N/A decisions, and supersession remain preserved. |
| `AC-GOV-021` | Event files and Git identities are authoritative; catalogs are derived. |
| `AC-GOV-022` | Receipt append uses expected-parent non-force CAS, idempotency, conflict detection, and bounded retry. |
| `AC-GOV-023` | Policy/member/cohort/pilot/configuration/recovery lifecycles are closed and exact-cardinality enforced. |
| `AC-GOV-024` | Legacy-v1 and historical-v2 remain readable/unchanged; conversion is receipt-bound. |
| `AC-GOV-025` | Validation is proportional, mutation-negative, exact-head-bound, and preserves applicable merge gates. |

## 26. Required architecture-review closure tests

An independent architecture review must verify:

1. every repository-truth finding `RT-GOV-AUTO-WP01-F-001` through `-008` has a concrete architectural disposition;
2. the receipt writer, permissions, ruleset bypass, trigger, CAS, readback, freeze, and recovery design is non-circular;
3. the selected App does not receive broader permissions than required;
4. a receipt write cannot mutate the candidate;
5. event authority cannot be satisfied by a catalog;
6. `GITHUB_TOKEN` trigger limitations do not create an unverified second-run dependency;
7. context tiers cannot self-upgrade;
8. technical validity, acceptance, eligibility, authorization, prompt, handoff, and readiness remain separate;
9. policy members cannot inherit cohort or other-member authority;
10. every pilot and configuration action remains separately authorized;
11. WP-GOV-24B exact-one-successor behavior is preserved;
12. corrective implementers cannot create qualifying findings or verify their own fixes;
13. history and failed evidence cannot be erased by recovery;
14. legacy-v1/v2 preservation and v3 conversion are explicit;
15. Drive topology has one nearest owner and no parent duplication;
16. unavailable ruleset/local/credential/configuration evidence remains a later gate, not an assumed fact.

## 27. Finding disposition

| Finding | ADR-020 disposition |
|---|---|
| `RT-GOV-AUTO-WP01-F-001` | Addressed by dedicated App issuer, same-run verification, exact ruleset/bootstrap ordering, and emergency freeze/recovery boundary. |
| `RT-GOV-AUTO-WP01-F-002` | Addressed architecturally by claim-only import, local evidence requirement, preservation-first classification, and no inferred cleanup. |
| `RT-GOV-AUTO-WP01-F-003` | Addressed by controller-issued attestation records, provider tiers, non-self-upgrade, and exact separation proof. |
| `RT-GOV-AUTO-WP01-F-004` | Addressed by mandatory direct export, desired-state diff, independent validation, and separate rollback authority before mutation. |
| `RT-GOV-AUTO-WP01-F-005` | Addressed by three-way authoritative head comparison and required negative fixture. |
| `RT-GOV-AUTO-WP01-F-006` | Addressed by selecting an AEOS package-local `policies/` folder and child index, subject to later publication authorization. |
| `RT-GOV-AUTO-WP01-F-007` | Addressed by provider adapter separation, disposable target, exact preflight, distinct restoration/rollback, and stop rules. |
| `RT-GOV-AUTO-WP01-F-008` | Addressed by exact non-force CAS, idempotency, five-attempt contention, post-write ancestry/blob verification, and pilot proof requirement. |

These are architecture claims only. Independent review determines whether they close the findings. Implementation and pilot evidence remain required.

## 28. Consequences and residual gates

### 28.1 Positive consequences

- Review evidence no longer invalidates the reviewed candidate.
- Standing policy effect becomes deterministic and member-specific.
- Receipt concurrency is bounded and loss-resistant.
- Context trust is explicit rather than self-asserted.
- Configuration recovery has one unambiguous path per outcome.
- Drive remains useful without becoming an execution ledger.
- Operator involvement can be reduced for routine eligible actions while preserving critical exceptions.

### 28.2 Costs

- A dedicated GitHub App and protected receipt branch add operational complexity.
- Event folding, context adapters, and exact-cardinality validators require substantial implementation and focused testing.
- Some current external-model sessions will remain ineligible for standing acceptance until a trusted attestation gateway exists.
- Configuration and ruleset pilots require disposable targets and exact rollback evidence.
- Historical branch/worktree uncertainty remains blocked until local evidence is available.

### 28.3 Unavailable evidence and future gates

Still unverified:

- actual current rulesets, branch protection, required checks, bypass actors, and auto-delete settings;
- App creation/install feasibility and credential storage;
- receipt-branch ruleset behavior in this repository;
- real concurrent ref-update behavior and API status handling;
- local branches, worktrees, dirty state, locks, and process dependencies;
- provider-native immutable session/log capabilities;
- safe configuration target and exact rollback APIs;
- Drive permissions for the selected publication topology.

These gaps block implementation/pilot activation where applicable but do not invalidate the architectural choice.

## 29. External specifications

The implementation must be validated against current GitHub documentation, including:

- REST Git references: `https://docs.github.com/en/rest/git/refs`
- `GITHUB_TOKEN` event behavior: `https://docs.github.com/en/actions/concepts/security/github_token`
- Workflow token permissions: `https://docs.github.com/en/actions/using-jobs/assigning-permissions-to-jobs`
- Repository rulesets and bypass actors: `https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets`
- Rulesets REST API: `https://docs.github.com/en/rest/repos/rules`

External documentation informs platform mechanics; authenticated repository and runtime evidence remain authoritative for actual configuration and behavior.

## 30. Next gate

If this exact ADR candidate passes independent architecture review, a separate operator decision may accept the architecture and authorize rebaselined implementation planning.

Architecture review does not authorize implementation or any receipt, App, credential, ruleset, configuration, policy, pilot, Drive, merge, cleanup, deployment, production, or risk action.
