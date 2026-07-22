---
title: "AEOS Standing Policy and Receipt Control Plane"
artifact_id: "ADR-020"
classification: "ADRs"
artifact_type: "Architectural Decision Record"
version: "0.3"
status: "Proposed R3 — Fresh Independent Architecture Review Required"
date_created: "2026-07-22"
date_updated: "2026-07-22"
revision: "R3 preservation and exactness corrective architecture"
controlling_review_id: "REVIEW-ADR-020-AEOS-STANDING-POLICY-R2-20260722-01"
controlling_review_sha256: "844d8d572d3fe3da669d5d02a0c1cc997c372c1b6cc9119872c0017f648c5457"
controlling_review_disposition: "REVISE"
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

### 2.1 R3 corrective scope and normative preservation

R3 is composed from the exact R1 normative source at reviewed head `a6f7b21521283824709cbcfb8ee828bdd9703dcc`, source-byte SHA-256 `3d4930c5642b2a7df1ffdf1bf29028c184c5a8f741ed51246691a91938b6c372`, Git blob `7d37fd50f250919127c351aa2fa1a71281656e43`. The complete R1 body is current normative content unless a control is explicitly classified in the R3 preservation matrix as `RETAINED_WITH_AUTHORIZED_CORRECTION` or `INTENTIONALLY_SUPERSEDED_WITH_RATIONALE`.

R3 preserves the independent R2 closure decisions that `ARCH-AEOS-GOV-AUTO-ADR020-R1-F-001` and `ARCH-AEOS-GOV-AUTO-ADR020-R1-F-002` are `VERIFIED_FIXED`. It addresses, without claiming verification:

- `ARCH-AEOS-GOV-AUTO-ADR020-R1-F-003` — separate logical-claim, event-identity, conflict, authorization-cardinality, role-order, and successor-cardinality contracts;
- `ARCH-AEOS-GOV-AUTO-ADR020-R1-F-004` — exact post-consumption state/successor routes for every matrix tuple and evaluator error;
- `ARCH-AEOS-GOV-AUTO-ADR020-R1-F-005` — mandatory positive reviewed-extension fixture in addition to closed-schema negative fixtures;
- `ARCH-AEOS-GOV-AUTO-ADR020-R2-F-001` — restoration of all unaffected R1 architecture and explicit preservation accounting.

The architecture evidence contains a heading-by-heading and control-family preservation matrix. No implementation, policy activation, receipt creation, platform configuration, or later lifecycle action is authorized. R3 claims only `ADDRESSED_IN_ADR020_R3` for open findings.

## 3. Decision summary

Adopt a repository-hosted, event-sourced AEOS control plane with these properties:

1. **Static definitions on `main`.** Normative standards, schemas, policy source versions, policy-to-pilot mappings, manifests, validators, workflows, and human-readable governance remain ordinary reviewed repository content.
2. **Dynamic evidence on a dedicated receipt branch.** Accepted reviews, acceptance decisions, policy evaluations, authorizations, action starts/results, handoffs, transitions, suspension, recovery, and activation decisions are immutable events on `refs/heads/aeos/receipts`.
3. **One trusted receipt writer with layered protection.** A dedicated GitHub App installation named conceptually `aeos-receipt-controller` is the only routine writer. It may bypass only the writer-restriction ruleset; it cannot bypass the independent receipt-history safety ruleset that prohibits deletion, rewind, force, and non-fast-forward changes.
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

Review acceptance has two mutually exclusive routes after technical validity passes:

1. **Standing-policy acceptance** requires the exact review-acceptance policy member to be `ACTIVE`, policy eligibility `ELIGIBLE`, an eligible trusted context tier, and no freeze, suspension, drift, or conflict.
2. **One-off operator acceptance** requires an exact operator decision bound to the review artifact hash and reviewed repository head. It does not require standing-policy eligibility and is the compatibility/bootstrap path for technically valid `DOCUMENTED_C` reviews and for the initial ADR/policy family.

Both routes append or preserve an immutable acceptance receipt. Neither route issues implementation, merge, cleanup, publication, deployment, production, credential, configuration, or risk authority. `DOCUMENTED_C` remains ineligible for automatic acceptance even after manual acceptance.

A blocking review may become an `ACCEPTED_BLOCKING_DETERMINATION` under the same integrity rules. That acceptance permits only a separately authorized bounded corrective route; it does not make the implementation acceptable.

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

The selected controller performs validate → append → readback verification in one run. The dedicated App provides a stable installation identity and may bypass only the writer-restriction layer needed for routine fast-forward appends. It is never a bypass actor for the independent history-safety layer. The architecture does not require push recursion.

### 8.3 Workflow entry

Permitted entry events are:

- `workflow_call` from accepted AEOS workflows;
- `workflow_dispatch` with schema-validated inputs for operator-directed recovery or pilot use;
- `repository_dispatch` from an approved harness gateway.

Untrusted pull-request code does not execute in a privileged receipt-writing context. `pull_request_target` is prohibited for running candidate-controlled scripts or consuming receipt credentials.

### 8.4 Protection and bootstrap ordering

Receipt capability is bootstrapped in this order, with a separate authorization for every mutating stage:

1. Export current rulesets, branch protection, workflow permissions, App installations, and relevant repository settings.
2. Independently validate the export and calculate the exact desired-state diff.
3. Create/install the dedicated App and credential only under `OP-EXC-006`.
4. Create `aeos/receipts` with a deterministic root manifest commit.
5. Apply `AEOS-RECEIPT-HISTORY-SAFETY` to the literal ref `refs/heads/aeos/receipts`.
6. Independently validate that the safety ruleset has no bypass actors.
7. Apply `AEOS-RECEIPT-WRITER-RESTRICTION` to the same literal ref, naming only the dedicated App installation as the routine update bypass actor.
8. Independently validate the aggregate ruleset readback and most-restrictive effective behavior.
9. Run a non-action shadow receipt append against synthetic evidence.
10. Run bounded safety, contention, idempotency, replay, and recovery pilots.
11. Only after all infrastructure pilots pass may policy behavioral pilots begin.

#### 8.4.1 Non-bypassable history-safety ruleset

`AEOS-RECEIPT-HISTORY-SAFETY` is active, targets only `refs/heads/aeos/receipts`, and has **no routine or administrative bypass actor**. It must:

- prohibit ref deletion;
- prohibit force updates, rewind, and every non-fast-forward update;
- require linear history;
- reject updates whose new commit is not a descendant of the authenticated current tip;
- remain applicable to the dedicated App.

The routine App cannot disable, edit, or bypass this ruleset. Emergency recovery requires a hard freeze, credential disablement or revocation as applicable, exact operator authorization under `OP-EXC-004`, `OP-EXC-006`, and `OP-EXC-010`, direct export, independent review of the recovery change, and post-change readback. Recovery changes the platform rule configuration; it never rewrites accepted receipt history.

#### 8.4.2 Routine-writer restriction ruleset

`AEOS-RECEIPT-WRITER-RESTRICTION` separately restricts routine ref updates. The dedicated App installation is the only routine bypass actor for the **update restriction only**. The more restrictive safety ruleset remains cumulative and controlling. Repository administrators, generic users, teams, deploy keys, workflows using `GITHUB_TOKEN`, and other Apps have no routine update bypass.

The controller is compiled with and validates all of these constants before token use:

```text
repository_id = <exact installed repository id>
installation_id = <exact dedicated App installation id>
receipt_ref = refs/heads/aeos/receipts
```

The caller cannot supply a repository, installation, branch, tag, or ref input. Any mismatch is `RECEIPT_TARGET_IDENTITY_CONFLICT`, triggers suspension, and produces no write.

Required checks on candidate branches are configured separately. Receipt persistence cannot depend on a check that runs only after the protected write, because that creates a bootstrap/deadlock cycle.

## 9. Receipt event and CAS protocol

### 9.1 Canonical event

Every authoritative event uses a closed v3 envelope and RFC 8785 JSON Canonicalization Scheme (JCS). Input must satisfy I-JSON, reject duplicate member names, invalid Unicode and non-finite numbers, and encode canonical output as UTF-8. No normalization outside RFC 8785 is applied.

R3 separates six identities that implementations must not collapse:

1. **Logical claim key** — identifies one governed operation across its permitted event chain.
2. **Full event identity** — identifies one exact immutable event.
3. **Chain-invariant conflict projection** — fields that must remain identical across all events in one claim.
4. **Authorization-cardinality key** — proves one authorization can reserve at most one claim.
5. **Event-role key and order** — permits only the closed ordered role sequence and cardinalities.
6. **Successor-cardinality key** — proves at most one applicable successor authority and handoff.

The closed logical claim key is:

```json
{
  "scope_version": 1,
  "repository_id": "<stable GitHub repository id>",
  "goal_id": "<exact goal>",
  "work_item_id": "<exact work item>",
  "action_class": "<closed action-class enum>",
  "logical_operation_id": "<controller-derived immutable operation id>",
  "attempt_id": "<exact authorized attempt>"
}
```

`logical_operation_id` is controller-derived from the reviewed work-item identity, governed resource slot, and action class. It is not caller-selected. Request ID, authorization ID, target state/SHA, event role, role payload, and successor identity are deliberately excluded from the logical claim key so that changes to those values are detectable conflicts within the same operation.

The chain-invariant conflict projection is a closed object containing:

```text
logical_claim_key
request_identity
review/policy/context identities
authorization_id
authorized repository/base/head/target identity
action class and prohibited actions
manifest/mapping/schema versions
```

Every event in one claim must have an identical JCS hash of this projection. A difference is `IDEMPOTENCY_SCOPE_CONFLICT` and suspends the affected scope.

The authorization-cardinality key is the JCS SHA-256 of:

```json
{
  "repository_id": "<id>",
  "authorization_id": "<id>",
  "action_class": "<enum>"
}
```

One authorization-cardinality key may be associated with exactly one logical claim key and at most one `AUTHORIZATION_CONSUMPTION_RESERVED` event. Reuse with a different claim or attempt is `AUTHORIZATION_CARDINALITY_VIOLATION`.

The full identity-bearing event object is closed and contains:

```json
{
  "envelope_version": "AEOS_RECEIPT_EVENT_V1",
  "event_schema_id": "<closed schema id and version>",
  "repository_id": "<stable GitHub repository id>",
  "receipt_ref": "refs/heads/aeos/receipts",
  "logical_claim_key": {},
  "chain_invariant_projection": {},
  "event_role": "<closed role enum>",
  "role_instance_id": "<closed role-specific identity>",
  "role_sequence": 0,
  "occurred_at": "<RFC 3339 UTC timestamp with Z>",
  "event_payload": {},
  "successor_identity": null
}
```

The closed one-use action-chain role contract is:

| Role | Cardinality | Required predecessor | Notes |
|---|---:|---|---|
| `AUTHORIZATION_CONSUMPTION_RESERVED` | exactly 1 | none | first role; reserves the authorization-cardinality key |
| `ACTION_NOT_STARTED` | 0..1 | reservation | terminal zero-effect branch; mutually exclusive with `ACTION_STARTED` |
| `ACTION_STARTED` | 0..1 | reservation | records provider request identity |
| `ACTION_RESULT` | 0..1 | `ACTION_STARTED` | terminal provider result for the attempt |
| `INDEPENDENT_VALIDATION` | 0..N | result or not-started | each required `validation_slot_id` exactly once |
| `SUCCESSOR_AUTHORIZATION_ISSUED` | 0..1 | terminal result plus required validation | one exact successor only |
| `AUTHORIZED_HANDOFF_ISSUED` | 0..1 | successor authorization | cannot create or widen authority |
| `TRANSITION_RECORDED` | 0..1 | authorized handoff | records, but does not self-authorize, transition |

A role key is `(logical_claim_key_hash, event_role, role_instance_id)`. An identical replay of the same role key and canonical bytes is `IDEMPOTENT_EXISTING`. Different bytes for the same role key are `IDEMPOTENCY_ROLE_CONFLICT`. A second reservation, out-of-order role, mutually exclusive role, excess cardinality, or missing required predecessor is `IDEMPOTENCY_CARDINALITY_VIOLATION` or `IDEMPOTENCY_CHAIN_ORDER_VIOLATION` and suspends the scope.

The successor-cardinality key is `(logical_claim_key_hash, successor_action_class)`. At most one applicable `SUCCESSOR_AUTHORIZATION_ISSUED` may exist for a claim. A second identical successor is idempotent; a different successor, target, scope or authority is `IDEMPOTENCY_SUCCESSOR_CONFLICT` and suspends both candidates.

Let `B = JCS(identity_bearing_object)` and `L` be the unsigned 64-bit big-endian byte length of `B`. The event ID is:

```text
event_id = lowerhex(
  SHA-256(
    UTF8("AEOS-RECEIPT-EVENT-ID\u0000V1\u0000")
    || L
    || B
  )
)
```

`event_id` is excluded from `B`. The stored object is exactly `{"event_id": event_id, "identity": identity_bearing_object}` serialized with RFC 8785. Its SHA-256 is the payload hash. The event path is frozen once from `occurred_at` and `event_id` as `events/<UTC-YYYY>/<UTC-MM>/<event_id>.json`. Different bytes under one event ID are `RECEIPT_ID_CONFLICT` and trigger global integrity review.

### 9.2 Append algorithm

Before attempt one the controller freezes the complete canonical object and bytes, timestamp, event ID, event path, logical claim key, chain-invariant projection, authorization-cardinality key, role key, successor key where applicable, request, context, authorization, attempt, target and repository identities. Retry may change only authenticated parent tip, tree, commit and non-force ref-update objects; crossing a UTC month boundary cannot change content or path.

Global resolution uses authoritative event history, not only the calculated path or a derived catalog:

1. Resolve the logical claim key across verified event blobs and ancestry.
2. Verify all chain-invariant projections are identical.
3. Verify the authorization-cardinality key maps to no other claim and has at most one reservation.
4. Validate role order, predecessor, mutual exclusion and cardinality.
5. Validate the successor-cardinality key and exact successor.
6. Return `IDEMPOTENT_EXISTING` only for identical canonical bytes at an already valid role key.
7. Suspend on scope, role, order, cardinality, authorization or successor conflict.

Mutation outcomes are normative:

| One-field mutation | Required outcome |
|---|---|
| request ID or request payload hash | same logical claim → `IDEMPOTENCY_SCOPE_CONFLICT` |
| authorization ID | same logical claim → `IDEMPOTENCY_SCOPE_CONFLICT`; reuse of old authorization elsewhere → `AUTHORIZATION_CARDINALITY_VIOLATION` |
| target identity or target SHA | same logical claim → `IDEMPOTENCY_SCOPE_CONFLICT` |
| event role | permitted only as the exact next closed role; duplicate identical role is idempotent; duplicate/out-of-order role fails cardinality/order |
| event payload | same role key with different bytes → `IDEMPOTENCY_ROLE_CONFLICT` |
| successor identity | second different successor → `IDEMPOTENCY_SUCCESSOR_CONFLICT` |
| attempt ID | new logical claim only with a new authorization after the prior claim is terminal; same authorization triggers `AUTHORIZATION_CARDINALITY_VIOLATION` |
| scope version | unknown version → `IDEMPOTENCY_SCOPE_VERSION_UNKNOWN`; a reviewed new version requires explicit migration and a new claim namespace |

For one append operation:

1. Authenticate repository, exact App installation, literal receipt ref, workflow/run and freeze state.
2. Validate schemas, context, exact head, policy/member state, authorization, frozen bytes, projections and global-history result.
3. Read receipt tip `T0`.
4. Create one blob and a tree derived from `T0` adding exactly the frozen event path.
5. Create commit `C1` with sole parent `T0`.
6. Update literal `refs/heads/aeos/receipts` to `C1` with expected parent `T0` and `force:false`.
7. On contention preserve the complete attempted evidence, reread authoritative history and retry at most five total attempts without changing content-level values.
8. After success, read back the ref, commit, tree, blob and exact bytes; verify parent, path, payload, issuer, installation, context, projections and event ID. If later appends advanced the branch, prove `C1` ancestry and identical blob resolution.
9. Emit exact append evidence.

No force update, reset, rebase, fallback row, first-match routing, caller-selected ref, timestamp regeneration, event regeneration or lost-update overwrite is permitted.

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

A reservation is terminal for that authorization. If no action starts and direct zero-effect evidence exists, a new authorization may be requested. Ambiguous provider acceptance suspends the scope; the old authorization is never reused. The chain roles, authorization-cardinality key and successor-cardinality key defined in 9.1 are mandatory: one authorization cannot reserve two attempts, and one terminal claim cannot issue two applicable successors.

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

Closed acceptance results are:

```text
ACCEPTED_BY_OPERATOR
ACCEPTED_BY_STANDING_POLICY
ACCEPTED_BLOCKING_DETERMINATION
CONDITIONAL_PENDING_VERIFICATION
NOT_ACCEPTED
INELIGIBLE
SUSPENDED
```

`ACCEPTED_BY_OPERATOR` is a one-off manual route and is independent of standing-policy eligibility. It requires:

- `technical_review_validity = VALID_PASSING`;
- exact review artifact ID, source hash, reviewed artifact identity, repository, base, and reviewed head;
- an exact operator identity and decision record;
- no stale head, tamper, conflict, supersession, or `INSUFFICIENT_EVIDENCE`;
- an immutable operator acceptance receipt.

For pre-receipt bootstrap under the current operator-governed AEOS process, the immutable receipt is a source-byte-preserved operator decision artifact with stable ID, exact hash, timestamp, actor, review ID/hash, reviewed head, scope, and explicit non-authority statement. After the receipt controller is available, it appends `OPERATOR_ACCEPTANCE_IMPORTED` referencing the original bytes and hash before that acceptance can participate in standing-policy bootstrap. Import preserves the original decision; it does not create new authority or upgrade context tier.

For post-bootstrap operation, the controller appends `REVIEW_ACCEPTED_BY_OPERATOR` directly to `aeos/receipts`. The standing-policy route appends `REVIEW_ACCEPTED_BY_STANDING_POLICY`. Exactly one acceptance route may be effective for a review version. A later duplicate with identical semantics is idempotent; a conflicting route or decision suspends acceptance.

`DOCUMENTED_C` may receive `ACCEPTED_BY_OPERATOR` when technical validity passes. It remains categorically ineligible for `ACCEPTED_BY_STANDING_POLICY` and cannot be upgraded by the acceptance event.

| Technical validity | Context tier | Operator decision | Active auto-accept member | Result | Action authority |
|---|---|---|---|---|---|
| `VALID_PASSING` | `DOCUMENTED_C` | exact accept | any | `ACCEPTED_BY_OPERATOR` | none |
| `VALID_PASSING` | `ATTESTED_A/B` | exact accept | any | `ACCEPTED_BY_OPERATOR` | none |
| `VALID_PASSING` | eligible attested tier | absent | exact member `ACTIVE` and eligible | `ACCEPTED_BY_STANDING_POLICY` | none |
| `VALID_PASSING` | `DOCUMENTED_C` | absent | any | `INELIGIBLE` | none |
| failing, stale, conflicting, superseded, or insufficient | any | accept or absent | any | `NOT_ACCEPTED` or `SUSPENDED` | none |

The validator rejects operator acceptance when technical validity is not `VALID_PASSING`, when review/head identity drifts, or when the decision artifact has unresolved fields. Acceptance never issues implementation, merge, cleanup, publication, deployment, production, credential, configuration, or risk authority.

### 12.4 Bootstrap and manual-acceptance closure fixtures

Architecture and implementation fixtures must prove:

1. the first ADR/policy family can be accepted through an exact operator acceptance artifact before auto-accept exists;
2. that artifact is imported without semantic change after receipt capability exists;
3. a technically valid `DOCUMENTED_C` review can become `ACCEPTED_BY_OPERATOR`;
4. the same review cannot become `ACCEPTED_BY_STANDING_POLICY`;
5. failing, stale, conflicting, superseded, or insufficient reviews cannot use the operator route;
6. duplicate identical operator acceptance is idempotent;
7. conflicting operator and standing-policy acceptance events suspend the review scope;
8. no acceptance result creates action authorization.

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

Closed `preflight_mode` values are:

```text
RETAIN_AFTER_PASS
RESTORE_AFTER_PASS
```

The configuration plan also declares `expected_effect` as `RETAINED_STATE` or `TEMPORARY_STATE`. Before apply authorization is issued, the exact preflight table is:

| Preflight mode | Expected effect | Pre-apply classification | Authorization |
|---|---|---|---|
| `RETAIN_AFTER_PASS` | `RETAINED_STATE` | `VALID_PREFLIGHT` | MAY_BE_REQUESTED |
| `RETAIN_AFTER_PASS` | `TEMPORARY_STATE` | `CONFIG_PREFLIGHT_MODE_CONTRADICTION` | PROHIBITED |
| `RESTORE_AFTER_PASS` | `TEMPORARY_STATE` | `VALID_PREFLIGHT` | MAY_BE_REQUESTED |
| `RESTORE_AFTER_PASS` | `RETAINED_STATE` | `CONFIG_PREFLIGHT_MODE_CONTRADICTION` | PROHIBITED |
| either | unknown/absent | `CONFIG_ROUTING_ENUM_UNKNOWN` | PROHIBITED |

This preflight rejection is separate from `WP-GOV-24B`. Once apply authority is consumed, every observed tuple is evaluated by the 48-cell post-consumption matrix below; none may return a pre-apply-only state.

After forward apply authority is consumed, terminal outcomes are limited to `PASS`, `FAIL`, `BLOCKED`, and `INSUFFICIENT_EVIDENCE`. Direct evidence classes are `RETAINED_STATE_VERIFIED`, `TEMPORARY_STATE_VERIFIED`, `ZERO_EFFECT_PROVEN`, `MUTATION_CONFIRMED_RECOVERY_KNOWN`, `MUTATION_CONFIRMED_RECOVERY_UNKNOWN_OR_UNSAFE`, and `MUTATION_OR_CONSUMPTION_AMBIGUOUS`.

The matrix is normative and exhaustive: `2 × 4 × 6 = 48` tuples. Each cell has one classification and one route. Every `VALID` tuple has exactly one successor; every `INTEGRITY_CONFLICT` has the single fail-closed suspension successor.

| Preflight mode | Outcome | Evidence class | Classification | Route-local result | Exact next action class | New authorization | Route | Normal continuation | Required closure evidence |
|---|---|---|---|---|---|---|---|---|---|
| `RETAIN_AFTER_PASS` | `PASS` | `RETAINED_STATE_VERIFIED` | `VALID` | `PILOT_PASS` | `PILOT_SEQUENCE_NEXT` | YES | `SEQUENCE_ADVANCE` | `NEW_AUTH_ONLY` | forward state and independent validation receipt |
| `RETAIN_AFTER_PASS` | `PASS` | `TEMPORARY_STATE_VERIFIED` | `INTEGRITY_CONFLICT` | `SUSPENDED` | `CONFIG_MODE_EVIDENCE_RECONCILIATION` | YES | `SUSPENSION_MODE_EVIDENCE_CONTRADICTION` | `PROHIBITED` | consumed authority plus mode/evidence contradiction, exact before/after export, plan and evaluator trace |
| `RETAIN_AFTER_PASS` | `PASS` | `ZERO_EFFECT_PROVEN` | `INTEGRITY_CONFLICT` | `SUSPENDED` | `RECEIPT_INTEGRITY_RECONCILIATION` | YES | `SUSPENSION` | `PROHIBITED` | PASS contradicts evidence class |
| `RETAIN_AFTER_PASS` | `PASS` | `MUTATION_CONFIRMED_RECOVERY_KNOWN` | `INTEGRITY_CONFLICT` | `SUSPENDED` | `RECEIPT_INTEGRITY_RECONCILIATION` | YES | `SUSPENSION` | `PROHIBITED` | PASS contradicts evidence class |
| `RETAIN_AFTER_PASS` | `PASS` | `MUTATION_CONFIRMED_RECOVERY_UNKNOWN_OR_UNSAFE` | `INTEGRITY_CONFLICT` | `SUSPENDED` | `RECEIPT_INTEGRITY_RECONCILIATION` | YES | `SUSPENSION` | `PROHIBITED` | PASS contradicts evidence class |
| `RETAIN_AFTER_PASS` | `PASS` | `MUTATION_OR_CONSUMPTION_AMBIGUOUS` | `INTEGRITY_CONFLICT` | `SUSPENDED` | `RECEIPT_INTEGRITY_RECONCILIATION` | YES | `SUSPENSION` | `PROHIBITED` | PASS contradicts evidence class |
| `RETAIN_AFTER_PASS` | `FAIL` | `RETAINED_STATE_VERIFIED` | `INTEGRITY_CONFLICT` | `SUSPENDED` | `RECEIPT_INTEGRITY_RECONCILIATION` | YES | `SUSPENSION` | `PROHIBITED` | FAIL contradicts verified retained/temporary state classification |
| `RETAIN_AFTER_PASS` | `FAIL` | `TEMPORARY_STATE_VERIFIED` | `INTEGRITY_CONFLICT` | `SUSPENDED` | `RECEIPT_INTEGRITY_RECONCILIATION` | YES | `SUSPENSION` | `PROHIBITED` | FAIL contradicts verified retained/temporary state classification |
| `RETAIN_AFTER_PASS` | `FAIL` | `ZERO_EFFECT_PROVEN` | `VALID` | `ABORTED_ZERO_EFFECT` | `NONE` | NO | `TERMINAL_NO_EFFECT` | `PROHIBITED` | direct zero-effect proof and failed validation receipt |
| `RETAIN_AFTER_PASS` | `FAIL` | `MUTATION_CONFIRMED_RECOVERY_KNOWN` | `VALID` | `ROLLBACK_REQUIRED` | `CONFIG_FAILURE_ROLLBACK` | YES | `FAILURE_ROLLBACK` | `PROHIBITED` | mutation proof plus exact recovery plan |
| `RETAIN_AFTER_PASS` | `FAIL` | `MUTATION_CONFIRMED_RECOVERY_UNKNOWN_OR_UNSAFE` | `VALID` | `SUSPENDED` | `OPERATOR_RECOVERY_ASSESSMENT` | YES | `SUSPENSION_UNSAFE_RECOVERY` | `PROHIBITED` | unsafe/unknown recovery evidence |
| `RETAIN_AFTER_PASS` | `FAIL` | `MUTATION_OR_CONSUMPTION_AMBIGUOUS` | `VALID` | `SUSPENDED` | `OPERATOR_RECONCILIATION` | YES | `SUSPENSION_AMBIGUOUS` | `PROHIBITED` | ambiguous mutation/consumption evidence |
| `RETAIN_AFTER_PASS` | `BLOCKED` | `RETAINED_STATE_VERIFIED` | `VALID` | `BLOCKED` | `OPERATOR_RECONCILIATION` | YES | `TERMINAL_BLOCKED` | `PROHIBITED` | retained state known but gate blocked |
| `RETAIN_AFTER_PASS` | `BLOCKED` | `TEMPORARY_STATE_VERIFIED` | `VALID` | `BLOCKED` | `OPERATOR_RECOVERY_ASSESSMENT` | YES | `TERMINAL_BLOCKED` | `PROHIBITED` | temporary state known; normal planned restoration not permitted after BLOCKED |
| `RETAIN_AFTER_PASS` | `BLOCKED` | `ZERO_EFFECT_PROVEN` | `VALID` | `BLOCKED` | `OPERATOR_RECONCILIATION` | YES | `TERMINAL_BLOCKED_ZERO_EFFECT` | `PROHIBITED` | zero-effect proof plus blocking reason |
| `RETAIN_AFTER_PASS` | `BLOCKED` | `MUTATION_CONFIRMED_RECOVERY_KNOWN` | `VALID` | `ROLLBACK_REQUIRED` | `CONFIG_FAILURE_ROLLBACK` | YES | `FAILURE_ROLLBACK` | `PROHIBITED` | blocked result plus exact mutation/recovery proof |
| `RETAIN_AFTER_PASS` | `BLOCKED` | `MUTATION_CONFIRMED_RECOVERY_UNKNOWN_OR_UNSAFE` | `VALID` | `SUSPENDED` | `OPERATOR_RECOVERY_ASSESSMENT` | YES | `SUSPENSION_UNSAFE_RECOVERY` | `PROHIBITED` | blocked result plus unsafe/unknown recovery |
| `RETAIN_AFTER_PASS` | `BLOCKED` | `MUTATION_OR_CONSUMPTION_AMBIGUOUS` | `VALID` | `SUSPENDED` | `OPERATOR_RECONCILIATION` | YES | `SUSPENSION_AMBIGUOUS` | `PROHIBITED` | blocked result plus ambiguous mutation/consumption |
| `RETAIN_AFTER_PASS` | `INSUFFICIENT_EVIDENCE` | `RETAINED_STATE_VERIFIED` | `VALID` | `SUSPENDED` | `EVIDENCE_RECONCILIATION` | YES | `SUSPENSION_EVIDENCE_GAP` | `PROHIBITED` | verified partial state plus unresolved required evidence |
| `RETAIN_AFTER_PASS` | `INSUFFICIENT_EVIDENCE` | `TEMPORARY_STATE_VERIFIED` | `VALID` | `SUSPENDED` | `EVIDENCE_RECONCILIATION` | YES | `SUSPENSION_EVIDENCE_GAP` | `PROHIBITED` | verified partial state plus unresolved required evidence |
| `RETAIN_AFTER_PASS` | `INSUFFICIENT_EVIDENCE` | `ZERO_EFFECT_PROVEN` | `VALID` | `SUSPENDED` | `EVIDENCE_RECONCILIATION` | YES | `SUSPENSION_EVIDENCE_GAP` | `PROHIBITED` | verified partial state plus unresolved required evidence |
| `RETAIN_AFTER_PASS` | `INSUFFICIENT_EVIDENCE` | `MUTATION_CONFIRMED_RECOVERY_KNOWN` | `VALID` | `ROLLBACK_REQUIRED` | `CONFIG_FAILURE_ROLLBACK` | YES | `FAILURE_ROLLBACK` | `PROHIBITED` | known mutation and recovery despite evidence gap |
| `RETAIN_AFTER_PASS` | `INSUFFICIENT_EVIDENCE` | `MUTATION_CONFIRMED_RECOVERY_UNKNOWN_OR_UNSAFE` | `VALID` | `SUSPENDED` | `OPERATOR_RECOVERY_ASSESSMENT` | YES | `SUSPENSION_UNSAFE_RECOVERY` | `PROHIBITED` | unknown/unsafe recovery and evidence gap |
| `RETAIN_AFTER_PASS` | `INSUFFICIENT_EVIDENCE` | `MUTATION_OR_CONSUMPTION_AMBIGUOUS` | `VALID` | `SUSPENDED` | `OPERATOR_RECONCILIATION` | YES | `SUSPENSION_AMBIGUOUS` | `PROHIBITED` | ambiguous mutation/consumption and evidence gap |
| `RESTORE_AFTER_PASS` | `PASS` | `RETAINED_STATE_VERIFIED` | `INTEGRITY_CONFLICT` | `SUSPENDED` | `CONFIG_MODE_EVIDENCE_RECONCILIATION` | YES | `SUSPENSION_MODE_EVIDENCE_CONTRADICTION` | `PROHIBITED` | consumed authority plus mode/evidence contradiction, exact before/after export, plan and evaluator trace |
| `RESTORE_AFTER_PASS` | `PASS` | `TEMPORARY_STATE_VERIFIED` | `VALID` | `PLANNED_RESTORATION_REQUIRED` | `CONFIG_PLANNED_RESTORATION` | YES | `PLANNED_RESTORATION` | `PROHIBITED_UNTIL_RESTORE_VALIDATED` | temporary state and forward validation receipt |
| `RESTORE_AFTER_PASS` | `PASS` | `ZERO_EFFECT_PROVEN` | `INTEGRITY_CONFLICT` | `SUSPENDED` | `RECEIPT_INTEGRITY_RECONCILIATION` | YES | `SUSPENSION` | `PROHIBITED` | PASS contradicts evidence class |
| `RESTORE_AFTER_PASS` | `PASS` | `MUTATION_CONFIRMED_RECOVERY_KNOWN` | `INTEGRITY_CONFLICT` | `SUSPENDED` | `RECEIPT_INTEGRITY_RECONCILIATION` | YES | `SUSPENSION` | `PROHIBITED` | PASS contradicts evidence class |
| `RESTORE_AFTER_PASS` | `PASS` | `MUTATION_CONFIRMED_RECOVERY_UNKNOWN_OR_UNSAFE` | `INTEGRITY_CONFLICT` | `SUSPENDED` | `RECEIPT_INTEGRITY_RECONCILIATION` | YES | `SUSPENSION` | `PROHIBITED` | PASS contradicts evidence class |
| `RESTORE_AFTER_PASS` | `PASS` | `MUTATION_OR_CONSUMPTION_AMBIGUOUS` | `INTEGRITY_CONFLICT` | `SUSPENDED` | `RECEIPT_INTEGRITY_RECONCILIATION` | YES | `SUSPENSION` | `PROHIBITED` | PASS contradicts evidence class |
| `RESTORE_AFTER_PASS` | `FAIL` | `RETAINED_STATE_VERIFIED` | `INTEGRITY_CONFLICT` | `SUSPENDED` | `RECEIPT_INTEGRITY_RECONCILIATION` | YES | `SUSPENSION` | `PROHIBITED` | FAIL contradicts verified retained/temporary state classification |
| `RESTORE_AFTER_PASS` | `FAIL` | `TEMPORARY_STATE_VERIFIED` | `INTEGRITY_CONFLICT` | `SUSPENDED` | `RECEIPT_INTEGRITY_RECONCILIATION` | YES | `SUSPENSION` | `PROHIBITED` | FAIL contradicts verified retained/temporary state classification |
| `RESTORE_AFTER_PASS` | `FAIL` | `ZERO_EFFECT_PROVEN` | `VALID` | `ABORTED_ZERO_EFFECT` | `NONE` | NO | `TERMINAL_NO_EFFECT` | `PROHIBITED` | direct zero-effect proof and failed validation receipt |
| `RESTORE_AFTER_PASS` | `FAIL` | `MUTATION_CONFIRMED_RECOVERY_KNOWN` | `VALID` | `ROLLBACK_REQUIRED` | `CONFIG_FAILURE_ROLLBACK` | YES | `FAILURE_ROLLBACK` | `PROHIBITED` | mutation proof plus exact recovery plan |
| `RESTORE_AFTER_PASS` | `FAIL` | `MUTATION_CONFIRMED_RECOVERY_UNKNOWN_OR_UNSAFE` | `VALID` | `SUSPENDED` | `OPERATOR_RECOVERY_ASSESSMENT` | YES | `SUSPENSION_UNSAFE_RECOVERY` | `PROHIBITED` | unsafe/unknown recovery evidence |
| `RESTORE_AFTER_PASS` | `FAIL` | `MUTATION_OR_CONSUMPTION_AMBIGUOUS` | `VALID` | `SUSPENDED` | `OPERATOR_RECONCILIATION` | YES | `SUSPENSION_AMBIGUOUS` | `PROHIBITED` | ambiguous mutation/consumption evidence |
| `RESTORE_AFTER_PASS` | `BLOCKED` | `RETAINED_STATE_VERIFIED` | `VALID` | `BLOCKED` | `OPERATOR_RECONCILIATION` | YES | `TERMINAL_BLOCKED` | `PROHIBITED` | retained state known but gate blocked |
| `RESTORE_AFTER_PASS` | `BLOCKED` | `TEMPORARY_STATE_VERIFIED` | `VALID` | `BLOCKED` | `OPERATOR_RECOVERY_ASSESSMENT` | YES | `TERMINAL_BLOCKED` | `PROHIBITED` | temporary state known; normal planned restoration not permitted after BLOCKED |
| `RESTORE_AFTER_PASS` | `BLOCKED` | `ZERO_EFFECT_PROVEN` | `VALID` | `BLOCKED` | `OPERATOR_RECONCILIATION` | YES | `TERMINAL_BLOCKED_ZERO_EFFECT` | `PROHIBITED` | zero-effect proof plus blocking reason |
| `RESTORE_AFTER_PASS` | `BLOCKED` | `MUTATION_CONFIRMED_RECOVERY_KNOWN` | `VALID` | `ROLLBACK_REQUIRED` | `CONFIG_FAILURE_ROLLBACK` | YES | `FAILURE_ROLLBACK` | `PROHIBITED` | blocked result plus exact mutation/recovery proof |
| `RESTORE_AFTER_PASS` | `BLOCKED` | `MUTATION_CONFIRMED_RECOVERY_UNKNOWN_OR_UNSAFE` | `VALID` | `SUSPENDED` | `OPERATOR_RECOVERY_ASSESSMENT` | YES | `SUSPENSION_UNSAFE_RECOVERY` | `PROHIBITED` | blocked result plus unsafe/unknown recovery |
| `RESTORE_AFTER_PASS` | `BLOCKED` | `MUTATION_OR_CONSUMPTION_AMBIGUOUS` | `VALID` | `SUSPENDED` | `OPERATOR_RECONCILIATION` | YES | `SUSPENSION_AMBIGUOUS` | `PROHIBITED` | blocked result plus ambiguous mutation/consumption |
| `RESTORE_AFTER_PASS` | `INSUFFICIENT_EVIDENCE` | `RETAINED_STATE_VERIFIED` | `VALID` | `SUSPENDED` | `EVIDENCE_RECONCILIATION` | YES | `SUSPENSION_EVIDENCE_GAP` | `PROHIBITED` | verified partial state plus unresolved required evidence |
| `RESTORE_AFTER_PASS` | `INSUFFICIENT_EVIDENCE` | `TEMPORARY_STATE_VERIFIED` | `VALID` | `SUSPENDED` | `EVIDENCE_RECONCILIATION` | YES | `SUSPENSION_EVIDENCE_GAP` | `PROHIBITED` | verified partial state plus unresolved required evidence |
| `RESTORE_AFTER_PASS` | `INSUFFICIENT_EVIDENCE` | `ZERO_EFFECT_PROVEN` | `VALID` | `SUSPENDED` | `EVIDENCE_RECONCILIATION` | YES | `SUSPENSION_EVIDENCE_GAP` | `PROHIBITED` | verified partial state plus unresolved required evidence |
| `RESTORE_AFTER_PASS` | `INSUFFICIENT_EVIDENCE` | `MUTATION_CONFIRMED_RECOVERY_KNOWN` | `VALID` | `ROLLBACK_REQUIRED` | `CONFIG_FAILURE_ROLLBACK` | YES | `FAILURE_ROLLBACK` | `PROHIBITED` | known mutation and recovery despite evidence gap |
| `RESTORE_AFTER_PASS` | `INSUFFICIENT_EVIDENCE` | `MUTATION_CONFIRMED_RECOVERY_UNKNOWN_OR_UNSAFE` | `VALID` | `SUSPENDED` | `OPERATOR_RECOVERY_ASSESSMENT` | YES | `SUSPENSION_UNSAFE_RECOVERY` | `PROHIBITED` | unknown/unsafe recovery and evidence gap |
| `RESTORE_AFTER_PASS` | `INSUFFICIENT_EVIDENCE` | `MUTATION_OR_CONSUMPTION_AMBIGUOUS` | `VALID` | `SUSPENDED` | `OPERATOR_RECONCILIATION` | YES | `SUSPENSION_AMBIGUOUS` | `PROHIBITED` | ambiguous mutation/consumption and evidence gap |


Route IDs deterministically project exact pilot, member and cohort effects:

| Route | Pilot outcome | Member-state effect | Cohort state |
|---|---|---|---|
| `SEQUENCE_ADVANCE` | `PASS` | `NO_MEMBER_STATE_CHANGE` | `PILOT_SEQUENCE_READY` |
| `PLANNED_RESTORATION` | `PASS_PENDING_PLANNED_RESTORATION` | `NO_MEMBER_STATE_CHANGE` | `PILOT_ASSESSMENT` |
| `FAILURE_ROLLBACK` | `FAIL` | `NO_MEMBER_STATE_CHANGE` | `ROLLBACK_REQUIRED` |
| `TERMINAL_NO_EFFECT` | `FAIL_ZERO_EFFECT` | `NO_MEMBER_STATE_CHANGE` | `OPERATOR_ACCEPTED_INACTIVE` |
| `TERMINAL_BLOCKED` | `BLOCKED` | `NO_MEMBER_STATE_CHANGE` | `RECONCILIATION_REQUIRED` |
| `TERMINAL_BLOCKED_ZERO_EFFECT` | `BLOCKED_ZERO_EFFECT` | `NO_MEMBER_STATE_CHANGE` | `RECONCILIATION_REQUIRED` |
| `SUSPENSION` | `BLOCKED_INTEGRITY_CONFLICT` | `NO_MEMBER_STATE_CHANGE` | `SUSPENDED` |
| `SUSPENSION_MODE_EVIDENCE_CONTRADICTION` | `BLOCKED_MODE_EVIDENCE_CONTRADICTION` | `NO_MEMBER_STATE_CHANGE` | `SUSPENDED` |
| `SUSPENSION_UNSAFE_RECOVERY` | `BLOCKED_UNSAFE_RECOVERY` | `NO_MEMBER_STATE_CHANGE` | `SUSPENDED` |
| `SUSPENSION_AMBIGUOUS` | `BLOCKED_AMBIGUOUS` | `NO_MEMBER_STATE_CHANGE` | `SUSPENDED` |
| `SUSPENSION_EVIDENCE_GAP` | `BLOCKED_EVIDENCE_GAP` | `NO_MEMBER_STATE_CHANGE` | `SUSPENDED` |

`NO_MEMBER_STATE_CHANGE` is a transition-effect marker: infrastructure configuration pilots cannot activate, suspend, revoke or expire an individual policy member. A member transition requires its own authorized event.

Evaluator failures also resolve to one complete fail-closed route:

| Error | Pilot outcome | Member effect | Cohort state | Exact next action | New authorization | Continuation | Required evidence |
|---|---|---|---|---|---|---|---|
| `CONFIG_SUCCESSOR_MISSING` | `BLOCKED_ROUTING_ERROR` | `NO_MEMBER_STATE_CHANGE` | `SUSPENDED` | `CONFIG_ROUTING_RECONCILIATION` | YES | PROHIBITED | exact tuple, table ID/version/hash, evaluator trace proving zero matches or zero successor |
| `CONFIG_SUCCESSOR_AMBIGUOUS` | `BLOCKED_ROUTING_ERROR` | `NO_MEMBER_STATE_CHANGE` | `SUSPENDED` | `CONFIG_ROUTING_RECONCILIATION` | YES | PROHIBITED | exact tuple, all matching rows/successors, table identity and evaluator trace |
| `CONFIG_ROUTING_ENUM_UNKNOWN` | `BLOCKED_SCHEMA_ERROR` | `NO_MEMBER_STATE_CHANGE` | `SUSPENDED` | `CONFIG_SCHEMA_RECONCILIATION` | YES | PROHIBITED | raw enum value, schema ID/version/hash, rejection trace and preserved input |

Validation rules:

- zero matching rows or a row with zero successor uses `CONFIG_SUCCESSOR_MISSING`;
- multiple matching rows or successors uses `CONFIG_SUCCESSOR_AMBIGUOUS`;
- unknown enum uses `CONFIG_ROUTING_ENUM_UNKNOWN`;
- `UNDECIDED`, `INELIGIBLE`, and `NOT_APPLICABLE` are prohibited after apply consumption;
- `BLOCKED` never advances the sequence;
- no tuple enters both planned restoration and failure rollback;
- planned restoration is reachable only from `RESTORE_AFTER_PASS + PASS + TEMPORARY_STATE_VERIFIED`;
- failure rollback is reachable only from a non-passing result with `MUTATION_CONFIRMED_RECOVERY_KNOWN`;
- successful failure rollback requires independent assessment, returns the cohort to `OPERATOR_ACCEPTED_INACTIVE`, and terminalizes the sequence as `ABORTED_ROLLED_BACK` without resume or continuation.

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

Every authoritative v3 object and every nested authority-bearing object is unconditionally closed with `additionalProperties: false`. All authority, receipt, context, review, policy, mapping, manifest, member, cohort, pilot, configuration, recovery, authorization, handoff, transition, checkpoint, and state enums are explicit and closed. Unknown top-level fields, nested fields, enum values, extension namespaces, or unresolved placeholders fail validation.

Extensibility, when retained, is allowed only through a field literally named `extensions`, whose value is a closed map of reviewed namespace keys to separately closed, versioned extension objects. Each extension schema must define its RFC 8785 canonical-hash inclusion, authority effect (`NONE` unless explicitly reviewed), evaluator behavior, compatibility rules, and activation version. Unknown namespaces or versions fail closed. No extension may add action authority, weaken a required field, alter an enum, or change evaluation until its schema version is independently reviewed and explicitly activated.

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

Schema-closure fixtures must reject unknown top-level, nested, enum, authorization, context, receipt, policy, mapping, manifest, pilot, configuration, recovery, handoff, transition, extension, namespace and version fields.

A mandatory positive fixture named `EXTENSION-FIXTURE-REVIEW-METADATA-V1` uses the reviewed namespace `com.hbpa.aeos.review-metadata`, version `1`, a separately closed payload containing only `version`, `reviewer_harness`, and `evidence_digest_sha256`, evaluator behavior `INFORMATIONAL_ONLY`, compatibility `IGNORE_ONLY_AFTER_SCHEMA_VALIDATION`, and authority effect `NONE`. Its exact fixture object is:

```json
{"extensions":{"com.hbpa.aeos.review-metadata":{"evidence_digest_sha256":"0000000000000000000000000000000000000000000000000000000000000000","reviewer_harness":"documented-c","version":1}}}
```

Its deterministic RFC 8785/JCS SHA-256 is `d4152d95229308157553d2ac6d17fe8cb5025eb24aabf2110f6927abb5d71340`. The fixture must prove namespace/version recognition, closed-payload validation, identical canonical bytes across implementations, exact hash inclusion in the containing authoritative record, consistent evaluator/compatibility behavior, authority effect `NONE`, and no authority expansion. Any field, namespace, version, hash or declared-effect mutation must fail closed.

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

### 24.10 Single receipt ruleset with App bypass

Rejected. A routine App bypass on the same ruleset that prohibits deletion and non-fast-forward history changes weakens platform enforcement. R3 retains the R2-selected cumulative layered rulesets: a non-bypassable history-safety layer plus a separate App writer-restriction layer.

### 24.11 Informal JSON concatenation and serializer conventions

Rejected. Informal field concatenation, key sorting, or implementation-defined number/string serialization is not a stable cryptographic identity contract. R3 retains RFC 8785 JCS plus a versioned domain separator and explicit length delimiter.

## 25. Acceptance criteria

| ID | Architecture criterion |
|---|---|
| `AC-GOV-001` | GitHub native review state is metadata and not a technical-review prerequisite. |
| `AC-GOV-002` | Substantive independent review remains mandatory where required. |
| `AC-GOV-003` | Reviews and receipts bind exact artifacts/repository heads without candidate mutation. |
| `AC-GOV-004` | Context evidence is trusted-issuer-created, unique, anti-replay, exact-scope, and risk-tiered. |
| `AC-GOV-005` | Review receipts include criteria, evidence, findings, limitations, disposition, context, and integrity. |
| `AC-GOV-006` | Blocking and insufficient dispositions cannot qualify as passing. |
| `AC-GOV-007` | Review acceptance uses either exact operator acceptance or the exact active policy member; acceptance is separate from every action authority. |
| `AC-GOV-008` | Validity, acceptance, eligibility, authorization, prompt, handoff, and readiness remain separate. |
| `AC-GOV-009` | Policy eligibility has no prompt/handoff dependency. |
| `AC-GOV-010` | Layered non-bypassable history safety plus drift, tamper, replay, contention, conflict, suspension, freeze, and undefined-transition controls fail closed. |
| `AC-GOV-011` | Implementation authority requires accepted design/plan and concrete exact binding. |
| `AC-GOV-012` | Corrective authority requires independent exact-head stable findings and closure tests. |
| `AC-GOV-013` | Merge requires current exact-head readiness and one-use authority. |
| `AC-GOV-014` | All consequential actions and every one of the 48 closed configuration tuples have distinct authorities/receipts and exact normative successors or fail-closed classifications. |
| `AC-GOV-015` | Drive publication is deterministic, read back, nearest-index registered, and non-authorizing. |
| `AC-GOV-016` | Operator exceptions preserve every enumerated high-consequence and secret boundary. |
| `AC-GOV-017` | Exception questions are narrow, expiring, evidence-bound, and fail closed. |
| `AC-GOV-018` | Every nonterminal consequential completion includes a complete non-authorizing successor prompt. |
| `AC-GOV-019` | Every executable transition has a separate authorization-bound handoff. |
| `AC-GOV-020` | Findings, failed evidence, contention, attempts, N/A decisions, supersession, and every unaffected R1 normative control remain preserved or explicitly dispositioned. |
| `AC-GOV-021` | Event files and Git identities are authoritative; catalogs are derived. |
| `AC-GOV-022` | Receipt append uses frozen RFC 8785 bytes, separate logical-claim/event/conflict/cardinality projections, expected-parent non-force CAS, exact chain ordering, and bounded retry. |
| `AC-GOV-023` | Authoritative v3 schemas and extensions, policy/member/cohort/pilot/configuration/recovery lifecycles, every 48-cell route, and every evaluator-error successor are closed and exact-cardinality enforced. |
| `AC-GOV-024` | Legacy-v1 and historical-v2 remain readable/unchanged; conversion is receipt-bound. |
| `AC-GOV-025` | Validation is proportional, mutation-negative, exact-head-bound, tests layered rulesets, claim/event/cardinality projections, all routing errors, schema closure, one positive extension, R1 preservation, and applicable merge gates. |

## 26. Required architecture-review closure tests

An independent architecture review must verify:

1. every R1 heading and normative control is present and classified `RETAINED_EXACTLY`, `RETAINED_WITH_AUTHORIZED_CORRECTION`, or `INTENTIONALLY_SUPERSEDED_WITH_RATIONALE`, with zero silent omissions;
2. the semantic delta from R1 is limited to the authorized findings and necessary metadata/evidence binding;
3. `ARCH-AEOS-GOV-AUTO-ADR020-R1-F-001` and `-002` remain fixed and are not weakened;
4. first-policy bootstrap and exact operator acceptance work without auto-accept circularity, grant no action authority, and leave `DOCUMENTED_C` ineligible for automatic acceptance;
5. the receipt-history safety ruleset has no routine bypass and remains applicable to the App, while the writer restriction permits only the exact App installation to attempt fast-forward updates to the literal receipt ref;
6. the App cannot delete, rewind, force-update, non-fast-forward-update, or target another ref through the controller;
7. RFC 8785 canonicalization is cross-language stable and rejects ambiguous concatenation, duplicate keys, invalid Unicode, non-finite numbers and unknown envelope fields;
8. logical claim key, event identity, chain-invariant projection, authorization-cardinality key, role key/order, and successor-cardinality key are distinct and independently tested;
9. one-field request, authorization, target, role, payload, successor, attempt and scope-version mutations produce the exact outcomes defined in section 9;
10. legitimate ordered multi-role chains pass, while second reservation, second conflicting successor, out-of-order role and same-role/different-bytes fail closed;
11. retry across a UTC month boundary preserves timestamp, path, event ID, bytes and all frozen projections;
12. concurrent identical requests produce one event plus idempotent readback, and conflicting requests suspend without duplicate authority;
13. event authority cannot be satisfied by a catalog or unverified derived index;
14. the preflight mode/expected-effect table rejects contradictions before authorization;
15. the 48-cell post-consumption matrix enumerates every tuple exactly once and maps each route to exact pilot, member-effect and cohort state;
16. every valid tuple has exactly one successor; `BLOCKED` never continues; planned restoration and failure rollback are mutually exclusive; successful rollback terminalizes `ABORTED_ROLLED_BACK`;
17. `CONFIG_SUCCESSOR_MISSING`, `CONFIG_SUCCESSOR_AMBIGUOUS`, and `CONFIG_ROUTING_ENUM_UNKNOWN` each produce the exact fail-closed state, action, authorization and evidence route;
18. all authoritative v3 top-level and nested authority-bearing objects reject unknown fields and enums;
19. unknown extension namespace/version fails closed and the mandatory positive reviewed-extension fixture has deterministic JCS bytes/hash, authority effect `NONE`, and no unintended expansion;
20. technical validity, acceptance, eligibility, authorization, prompt, handoff and readiness remain separate;
21. policy members cannot inherit cohort or other-member authority, and every pilot/configuration mutation remains separately authorized;
22. corrective implementers cannot create qualifying findings or verify their own fixes;
23. history and failed evidence cannot be erased by recovery;
24. legacy-v1/v2 preservation and v3 conversion remain explicit;
25. Drive topology has one nearest owner and no parent duplication;
26. every repository-truth finding `RT-GOV-AUTO-WP01-F-001` through `-008` has a concrete architectural disposition without implementation/runtime/platform/Drive overclaim;
27. unavailable ruleset, local, credential, configuration and runtime evidence remains a later gate rather than an assumed fact;
28. the fresh review request filename, bytes, SHA-256 sidecar, byte count, line count and terminal newline agree exactly.

## 27. Finding disposition

### 27.1 Architecture-review findings

| Finding | Controlling status and R3 claim |
|---|---|
| `ARCH-AEOS-GOV-AUTO-ADR020-R1-F-001` | `VERIFIED_FIXED` by independent R2 review; R3 retains operator acceptance, bootstrap import, manual `DOCUMENTED_C` acceptance, closed results and negative fixtures. |
| `ARCH-AEOS-GOV-AUTO-ADR020-R1-F-002` | `VERIFIED_FIXED` by independent R2 review; R3 retains layered non-bypassable history safety, separate App writer restriction, literal repository/installation/ref binding and emergency-only recovery. |
| `ARCH-AEOS-GOV-AUTO-ADR020-R1-F-003` | `ADDRESSED_IN_ADR020_R3` — separate claim/event/conflict/cardinality projections, closed role ordering and exact one-field mutation outcomes. |
| `ARCH-AEOS-GOV-AUTO-ADR020-R1-F-004` | `ADDRESSED_IN_ADR020_R3` — separated preflight rejection, exact 48 post-consumption routes, route state projections and complete evaluator-error successors. |
| `ARCH-AEOS-GOV-AUTO-ADR020-R1-F-005` | `ADDRESSED_IN_ADR020_R3` — unconditional closure retained plus mandatory deterministic positive reviewed-extension fixture. |
| `ARCH-AEOS-GOV-AUTO-ADR020-R2-F-001` | `ADDRESSED_IN_ADR020_R3` — complete R1 architecture restored and preservation matrix required; no unaffected control is silently absent. |

Only the two statuses explicitly verified by the independent R2 review are recorded as `VERIFIED_FIXED`. This authoring context does not verify its own R3 corrections.

### 27.2 Repository-truth findings

| Finding | ADR-020 R3 architectural disposition |
|---|---|
| `RT-GOV-AUTO-WP01-F-001` | Partially addressed by dedicated App issuer, same-run verification, layered non-bypassable safety, exact bootstrap ordering, and emergency freeze/recovery boundary; implementation and pilot proof remain required. |
| `RT-GOV-AUTO-WP01-F-002` | Addressed architecturally by claim-only import, local evidence requirement, preservation-first classification, and no inferred cleanup; direct local evidence remains unavailable. |
| `RT-GOV-AUTO-WP01-F-003` | Partially addressed by controller-issued attestation, provider tiers, no self-upgrade, exact separation proof, and explicit operator acceptance for `DOCUMENTED_C`; provider implementation remains unverified. |
| `RT-GOV-AUTO-WP01-F-004` | Addressed architecturally by mandatory direct export, exact desired-state diff, independent validation, separate restoration/rollback authority, and the normative routing matrix; platform proof remains required. |
| `RT-GOV-AUTO-WP01-F-005` | Addressed architecturally by three-way authoritative head comparison and required negative fixture; implementation proof remains required. |
| `RT-GOV-AUTO-WP01-F-006` | Partially addressed by selecting an AEOS package-local `policies/` folder and child index; creation, permissions, registration, and readback remain future evidence. |
| `RT-GOV-AUTO-WP01-F-007` | Partially addressed by provider adapter separation, disposable target, exact preflight, full routing matrix, distinct restoration/rollback, and stop rules; provider pilot evidence remains required. |
| `RT-GOV-AUTO-WP01-F-008` | Partially addressed by frozen RFC 8785 identity, global logical idempotency, exact non-force CAS, five-attempt contention, post-write ancestry/blob verification, and pilot proof requirements. |

These are architecture claims only. Independent review determines architecture closure. Implementation and pilot evidence remain required.


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
- Repository rulesets, cumulative evaluation, and bypass actors: `https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets`
- Available ruleset controls: `https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets`
- RFC 8785 JSON Canonicalization Scheme: `https://www.rfc-editor.org/rfc/rfc8785.html`
- Rulesets REST API: `https://docs.github.com/en/rest/repos/rules`

External documentation informs platform mechanics; authenticated repository and runtime evidence remain authoritative for actual configuration and behavior.

## 30. Next gate

If this exact ADR candidate passes independent architecture review, a separate operator decision may accept the architecture and authorize rebaselined implementation planning.

Fresh independent review of ADR-020 R3 does not authorize implementation or any receipt, App, credential, ruleset, configuration, policy, pilot, Drive, merge, cleanup, deployment, production, or risk action.
