---
title: "AEOS Standing Policy and Receipt Control Plane"
artifact_id: "ADR-020"
classification: "ADRs"
artifact_type: "Architectural Decision Record"
version: "0.2"
status: "Proposed R2 — Fresh Independent Architecture Review Required"
date_created: "2026-07-22"
date_updated: "2026-07-22"
revision: "R2 corrective architecture"
controlling_review_id: "REVIEW-ADR-020-AEOS-STANDING-POLICY-R1-20260722-01"
controlling_review_sha256: "a2dce8a18a19dcb69fcb05d95b3fbefade2c37259e783172ab31525a62ff8d35"
controlling_review_disposition: "REVISE"
decision_owner: "Bobby Fetting"
author: "OpenAI ChatGPT, operator-directed"
repository: "RMF112018/hb-personal-assistant"
branch: "arch/adr-020-aeos-governance-automation-r1"
base_sha: "b2b7bb63443bf5a098c2851eb101e4d5c148c589"
planning_artifact_id: "PLAN-AEOS-GOVERNANCE-AUTOMATION-AMENDMENT-001-R6"
planning_artifact_sha256: "0cc105b375f09bb5df712a13488dcaa07375520315f2b1dc708409eaf6421dd6"
---

# AEOS Standing Policy and Receipt Control Plane

## 1. Status and scope

This is proposed architecture only. It has no action effect until fresh exact-head review and separate operator acceptance. It authorizes no implementation, App/credential, receipt branch, ruleset/check, policy/pilot/configuration, Drive, merge, cleanup, deployment, production, or risk action. ADR-019 remains controlling.

R2 preserves unaffected R1 decisions and addresses only `ARCH-AEOS-GOV-AUTO-ADR020-R1-F-001` through `-005`. Claims are `ADDRESSED_IN_ADR020_R2`, never `VERIFIED_FIXED` by this authoring context.

## 2. Control-plane invariants

Static definitions remain reviewed files on `main`. Dynamic review, acceptance, policy, authorization, action, handoff, transition, suspension, recovery, and activation facts are immutable events on literal `refs/heads/aeos/receipts`. Event file plus Git commit/tree/blob and payload identity are authoritative; catalogs, snapshots, dashboards, and Drive summaries are derived.

```text
technical_review_validity
→ review_acceptance
→ action_policy_eligibility
→ action_authorization
→ handoff_readiness
→ transition_readiness
```

`REV-GATE-008` belongs to acceptance, not technical validity. One state is active per invocation; models request but do not activate the next state; eligibility has no prompt/handoff dependency; authorization precedes handoff; one authorization binds one action/target/attempt/exact identity; candidate branches are not mutated for receipts; exact member `ACTIVE` is required and cohort state grants no authority; implementers cannot establish their own corrective findings or verify fixes; planned restoration and failure rollback are distinct; merge, validation, cleanup, publication, deployment, production, and closure remain separate; secret lifecycle routes to `OP-EXC-006`; unavailable/conflicting material evidence fails closed.

Technical validity binds exact artifact/head, context, criteria/findings, evidence, limits, disposition, tamper/drift/replay, and successor prompt. Blocking, stale, conflicting, superseded, or insufficient reviews cannot pass. Acceptance never creates action authority. Authorization binds exact policy/version/member/mapping, repository/base/head/target, state/work item, action class, attempt/idempotency, review/findings/evidence, expiry/drift, and prohibited actions; issuance and consumption are separate events.

## 3. Operator review acceptance (`F-001`)

After `technical_review_validity=VALID_PASSING`, exactly one route may be effective:

- `ACCEPTED_BY_STANDING_POLICY`: eligible attested context, exact auto-accept member `ACTIVE`, policy eligibility, and no freeze/suspension/drift/conflict.
- `ACCEPTED_BY_OPERATOR`: exact operator decision bound to review ID/hash, reviewed artifacts, repository/base/head, disposition, timestamp, scope, and explicit non-authority statement. Standing-policy eligibility is not required.

A valid `DOCUMENTED_C` review may be manually accepted but remains ineligible for automatic acceptance; acceptance never upgrades context tier. Before receipt capability, bootstrap uses a source-byte-preserved operator-decision artifact with stable ID/SHA-256. After controller availability, `OPERATOR_ACCEPTANCE_IMPORTED` references those exact original bytes before policy bootstrap. Later manual acceptance appends `REVIEW_ACCEPTED_BY_OPERATOR`. Import changes no semantics and grants no action authority.

Closed results: `ACCEPTED_BY_OPERATOR`, `ACCEPTED_BY_STANDING_POLICY`, `ACCEPTED_BLOCKING_DETERMINATION`, `CONDITIONAL_PENDING_VERIFICATION`, `NOT_ACCEPTED`, `INELIGIBLE`, `SUSPENDED`.

| Validity | Context | Operator | Auto member | Result |
|---|---|---|---|---|
| passing | `DOCUMENTED_C` | exact accept | any | `ACCEPTED_BY_OPERATOR` |
| passing | attested | exact accept | any | `ACCEPTED_BY_OPERATOR` |
| passing | eligible attested | absent | active/eligible | `ACCEPTED_BY_STANDING_POLICY` |
| passing | `DOCUMENTED_C` | absent | any | `INELIGIBLE` |
| failing/stale/conflicting/superseded/insufficient | any | any | any | `NOT_ACCEPTED` or `SUSPENDED` |

Identical acceptance is idempotent; conflicting routes suspend. Fixtures prove first-policy bootstrap, manual `DOCUMENTED_C` acceptance, automatic rejection for it, rejection of invalid/stale reviews, and zero action authority.

## 4. Receipt writer and layered protection (`F-002`)

The routine writer is one dedicated least-privilege GitHub App installation: Metadata read; Contents read/write; Actions/Checks/PRs/Issues read; no Administration, Secrets, Environments, Deployments, Actions-write, PR-write, or Issues-write for receipt work. App creation/install/key/permission/rotation is operator-controlled `OP-EXC-006`. The controller validates, appends, and reads back in one run; it does not depend on receipt-push recursion and never runs candidate-controlled code in privileged `pull_request_target`.

Bootstrap actions are separately authorized: settings export; independent diff; App setup; deterministic root; safety ruleset; safety readback; writer restriction; aggregate readback; shadow/safety/contention/replay/recovery pilots; behavioral pilots.

`AEOS-RECEIPT-HISTORY-SAFETY` targets literal `refs/heads/aeos/receipts`, has no routine or administrative bypass actor, applies to the App, prohibits deletion/force/rewind/non-fast-forward, and requires linear history. Emergency change requires hard freeze, App disablement/revocation as applicable, exact operator authority under `OP-EXC-004/006/010`, export, independent review, one change, and readback; accepted history is never rewritten.

`AEOS-RECEIPT-WRITER-RESTRICTION` separately restricts routine updates; only the dedicated App bypasses that update restriction. Applicable rulesets are cumulative, so safety still controls. Controller constants are exact repository ID, installation ID, and literal receipt ref. Caller input cannot select repository, installation, branch, tag, or ref. Mismatch is `RECEIPT_TARGET_IDENTITY_CONFLICT`, suspends, and writes nothing. Tests prove valid fast-forward append and reject deletion, force, rewind, non-fast-forward, safety bypass, or another ref.

## 5. Canonical event identity and global idempotency (`F-003`)

Events use closed v3 objects and RFC 8785 JCS. Inputs satisfy I-JSON and reject duplicate keys, invalid Unicode, non-finite numbers, unknown fields, and placeholders. Canonical output is UTF-8.

The closed identity object, excluding `event_id`, contains: envelope version; schema ID/version; event type; stable repository ID; literal receipt ref; issuer-created request ID/payload SHA/issuer; closed idempotency scope (version, authorization, attempt, event role, target SHA); governed repository head/artifacts/policy-or-review identity; UTC timestamp; context attestation; payload.

Let `B=JCS(identity)` and `L=uint64_be(len(B))`:

```text
event_id = lowerhex(SHA-256(
  UTF8("AEOS-RECEIPT-EVENT-ID\u0000V1\u0000") || L || B
))
```

Stored bytes are JCS of `{"event_id":event_id,"identity":identity}`. Path is frozen as `events/<UTC-YYYY>/<UTC-MM>/<event_id>.json`.

Before attempt one, freeze identity/stored bytes, timestamp, event ID/path, request identity, idempotency scope/JCS hash, repository/installation/ref, context, policy/review, authorization, attempt, and target. Retry may change only parent, tree, commit, and non-force ref request; crossing a UTC month boundary changes nothing frozen.

Global idempotency folds authoritative event history; derived indexes only accelerate and every hit/absence is verified against authoritative blobs/ancestry:

- no prior scope: append may proceed;
- one identical event/role: `IDEMPOTENT_EXISTING`;
- same scope with different bytes/request/role/authorization/target/successor: `IDEMPOTENCY_SCOPE_CONFLICT`, suspend;
- multiple one-use claims: `IDEMPOTENCY_CARDINALITY_VIOLATION`, freeze consumption/successors.

Append uses current tip `T0`, one event blob/tree/commit with sole parent `T0`, and literal ref update `force:false`. Conflicts preserve evidence and retry at most five times with frozen content. Success is read back through ref/commit/tree/blob/bytes/issuer/context and later-tip ancestry. No force/reset/rebase/regeneration/caller-ref/fallback/first-match/lost-update is permitted. One authorization yields at most one reservation and successor chain. Fixtures cover ambiguous concatenation, cross-language JCS, key/numeric normalization, invalid JSON, UTC month rollover, identical/conflicting concurrency, replay after advance, second reservation, and exact-one successor.

## 6. Context, policy, pilot, and recovery

Context tiers are `ATTESTED_A`, `ATTESTED_B`, `DOCUMENTED_C`, `UNAVAILABLE`. Issuer, not model, creates ID/nonce. Review context/run/nonce/log/role differs from author and performs no candidate write. `DOCUMENTED_C` is technically reviewable but never auto-accept eligible.

Exact versioned members cover auto-accept, routing, implementation, corrective, merge, post-merge, closeout, and publication. Immutable mappings bind each member/version to ordered infrastructure and behavioral pilots; missing/duplicate/wildcard/range/prose/stale/reordered mappings fail closed. Member and cohort state are event folds; exact member `ACTIVE` is required. PASS does not activate policy; the operator selects the exact passing subset. Shared failure suspends cohort; member-local failure inactivates that member; resume requires new authority.

Corrective eligibility requires an independent exact-head blocking review/audit with stable finding IDs and closure tests. No finding is `INELIGIBLE/NOT_APPLICABLE`; implementers cannot create or verify their own finding.

Receipt integrity verifies root, linear ancestry, no delete/force, one event addition, schema/JCS/hash/issuer/context, global idempotency, and catalog rebuild. Failure freezes logically. Recovery is forward-only, preserves failed attempts, never rewrites history, and separates App/ruleset/credential/configuration authority. Operator exceptions retain business intent, architecture, material risk, destructive work, credentials/secrets, legal/privacy/compliance, conflicts/gaps, emergency, deployment, production, and risk acceptance. Nonterminal completions include a non-authorizing prompt; executable transitions require separate authorization-bound handoff.

## 7. Configuration and complete `WP-GOV-24B` routing (`F-004`)

Separate operations: export, feasibility, exact diff, apply, forward validation, planned restoration, restored validation, failure rollback, rollback assessment. Every mutation has distinct action class, authority, attempt, idempotency, and receipt. Target is disposable/unique and excludes `main`, release, production, secrets, deployments, and user work. Preflight binds raw before-state/hash, authenticated settings, API capability, desired state, recovery target, restore/delete semantics, and unrelated-rule exclusion. No proof means `INFEASIBLE` and no apply authority.

Closed codes:

- modes: `M1=RETAIN_AFTER_PASS`, `M2=RESTORE_AFTER_PASS`;
- outcomes: `O1=PASS`, `O2=FAIL`, `O3=BLOCKED`, `O4=INSUFFICIENT_EVIDENCE`;
- evidence columns: `E1=RETAINED_STATE_VERIFIED`, `E2=TEMPORARY_STATE_VERIFIED`, `E3=ZERO_EFFECT_PROVEN`, `E4=MUTATION_CONFIRMED_RECOVERY_KNOWN`, `E5=MUTATION_CONFIRMED_RECOVERY_UNKNOWN_OR_UNSAFE`, `E6=MUTATION_OR_CONSUMPTION_AMBIGUOUS`.

| Route | Classification; state; next action; new auth; continuation/evidence |
|---|---|
| `A` | valid; `PILOT_PASS`; `PILOT_SEQUENCE_NEXT`; yes; new authority only, retained-state validation |
| `B` | valid; `PLANNED_RESTORATION_REQUIRED`; `CONFIG_PLANNED_RESTORATION`; yes; no continuation until restore validation |
| `C` | invalid before apply; `AUTHORIZATION_PROHIBITED`; none; no; post-consumption observation suspends |
| `D` | integrity conflict; `SUSPENDED`; `RECEIPT_INTEGRITY_RECONCILIATION`; yes; contradictory evidence |
| `E` | valid; `ABORTED_ZERO_EFFECT`; none; no; terminal zero-effect proof |
| `F` | valid; `ROLLBACK_REQUIRED`; `CONFIG_FAILURE_ROLLBACK`; yes; mutation plus exact recovery |
| `G` | valid; `SUSPENDED`; `OPERATOR_RECOVERY_ASSESSMENT`; yes; unsafe/unknown recovery |
| `H` | valid; `SUSPENDED`; `OPERATOR_RECONCILIATION`; yes; ambiguous mutation/consumption |
| `I` | valid; `BLOCKED`; `OPERATOR_RECONCILIATION`; yes; retained state, no continuation |
| `J` | valid; `BLOCKED`; `OPERATOR_RECOVERY_ASSESSMENT`; yes; temporary state, no planned restore after block |
| `K` | valid; `BLOCKED`; `OPERATOR_RECONCILIATION`; yes; zero effect, no continuation |
| `L` | valid; `SUSPENDED`; `EVIDENCE_RECONCILIATION`; yes; partial state plus evidence gap |

This 8×6 matrix is normative and exhaustively classifies all 48 tuples; column order is E1..E6:

| Mode/outcome | E1 | E2 | E3 | E4 | E5 | E6 |
|---|---|---|---|---|---|---|
| `M1/O1` | A | C | D | D | D | D |
| `M1/O2` | D | D | E | F | G | H |
| `M1/O3` | I | J | K | F | G | H |
| `M1/O4` | L | L | L | F | G | H |
| `M2/O1` | C | B | D | D | D | D |
| `M2/O2` | D | D | E | F | G | H |
| `M2/O3` | I | J | K | F | G | H |
| `M2/O4` | L | L | L | F | G | H |

Exactly one cell applies. Zero match/successor is `CONFIG_SUCCESSOR_MISSING`; multiple is `CONFIG_SUCCESSOR_AMBIGUOUS`; unknown enum is `CONFIG_ROUTING_ENUM_UNKNOWN`. `UNDECIDED`, `INELIGIBLE`, and `NOT_APPLICABLE` are prohibited after apply consumption. `BLOCKED` never continues. Planned restoration is only M2/O1/E2. Failure rollback is only non-passing E4. No tuple enters both. Successful rollback is independently assessed and terminalizes `ABORTED_ROLLED_BACK`; it never resumes.

## 8. Mandatory v3 closure and compatibility (`F-005`)

Every authoritative v3 object and nested authority-bearing object is unconditionally closed with `additionalProperties:false`. All authority, receipt, context, review, acceptance, policy, mapping, manifest, member, cohort, pilot, configuration, recovery, authorization, handoff, transition, checkpoint, state, extension objects, and enums are closed. Unknown fields/enums/namespaces/versions/placeholders fail.

Extensions are permitted only through literal `extensions`, a closed map from reviewed namespace keys to separately closed versioned objects. Each defines RFC 8785 hash inclusion, evaluator behavior, compatibility, and authority effect (`NONE` unless explicitly reviewed). Unknown namespace/version fails; extensions cannot add authority, weaken fields, or alter enums until independently reviewed and explicitly activated.

```text
authorization.authorized_identity.repository_head
== authenticated_execution.repository_head
== state.repository.head_sha
```

Any mismatch fails, including one-side mutation fixtures. Negative fixtures cover unknown top-level, nested, enum, authorization, context, receipt, policy, pilot, configuration, recovery, handoff, transition, and extension fields.

Legacy v1 remains registry-bound/read-only. Historical v2 remains byte-preserved/readable. New active records use v3 only after accepted migration. Conversion requires an explicit receipt binding source/destination bytes, mapping, defaults, head, validation, context, and preservation; conversion never activates.

## 9. Historical and Drive boundaries

Prior branch/worktree records remain claims. Remote truth comes from GitHub; local worktrees/dirty state/locks/processes require local evidence. Absence is not deletion proof; uncertain state is preserved; PR #323 remains unresolved without cleanup evidence/authority.

Drive publication is post-merge and separately authorized. Nearest owner is the AEOS governance package, with later direct child `policies/` and `00_AEOS_STANDING_POLICY_INDEX.md`; parents register only the child package. Stable IDs, create/revise, representation/hash scope, readback, and registration are explicit. Publication never activates policy/action.

## 10. Acceptance criteria

| ID | Criterion |
|---|---|
| `AC-GOV-001` | Native review state is metadata, not a technical prerequisite. |
| `AC-GOV-002` | Substantive independent review remains mandatory. |
| `AC-GOV-003` | Exact review/receipt binding does not mutate candidate. |
| `AC-GOV-004` | Context is issuer-created, unique, anti-replay, exact-scope, risk-tiered. |
| `AC-GOV-005` | Review receipts preserve criteria/evidence/findings/limits/disposition/context/integrity. |
| `AC-GOV-006` | Blocking/insufficient reviews cannot pass. |
| `AC-GOV-007` | Acceptance uses exact operator decision or exact active member and grants no action authority. |
| `AC-GOV-008` | Decision layers remain separate. |
| `AC-GOV-009` | Eligibility has no prompt/handoff dependency. |
| `AC-GOV-010` | Layered safety and drift/tamper/replay/contention/conflict/freeze fail closed. |
| `AC-GOV-011` | Implementation requires accepted design/plan and exact binding. |
| `AC-GOV-012` | Corrective authority requires independent exact-head findings/tests. |
| `AC-GOV-013` | Merge requires exact-head readiness and one-use authority. |
| `AC-GOV-014` | Consequential actions and all 48 configuration tuples have exact route/authority. |
| `AC-GOV-015` | Drive publication is deterministic/read back/nearest-owner/non-authorizing. |
| `AC-GOV-016` | Critical operator/secret exceptions remain. |
| `AC-GOV-017` | Exceptions are narrow/expiring/evidence-bound/fail closed. |
| `AC-GOV-018` | Nonterminal consequential completion includes successor prompt. |
| `AC-GOV-019` | Executable transition requires authorization-bound handoff. |
| `AC-GOV-020` | Findings/failed evidence/attempts/contention/N-A/supersession persist. |
| `AC-GOV-021` | Event/Git identity authoritative; catalogs derived. |
| `AC-GOV-022` | Frozen JCS/global idempotency/non-force CAS/conflict/bounded retry required. |
| `AC-GOV-023` | V3 and policy/pilot/configuration/recovery are closed/exact-cardinality. |
| `AC-GOV-024` | V1/v2 unchanged/readable; conversion receipt-bound. |
| `AC-GOV-025` | Validation is proportional/negative/exact-head and covers rulesets/JCS/idempotency/closure. |

## 11. Finding reconciliation and tests

| Finding | R2 disposition |
|---|---|
| `ARCH-AEOS-GOV-AUTO-ADR020-R1-F-001` | `ADDRESSED_IN_ADR020_R2`: operator route/bootstrap/import/tests. |
| `ARCH-AEOS-GOV-AUTO-ADR020-R1-F-002` | `ADDRESSED_IN_ADR020_R2`: non-bypassable safety plus App writer restriction/literal target. |
| `ARCH-AEOS-GOV-AUTO-ADR020-R1-F-003` | `ADDRESSED_IN_ADR020_R2`: RFC 8785/domain/length/frozen retry/global idempotency. |
| `ARCH-AEOS-GOV-AUTO-ADR020-R1-F-004` | `ADDRESSED_IN_ADR020_R2`: exhaustive 48-tuple routing. |
| `ARCH-AEOS-GOV-AUTO-ADR020-R1-F-005` | `ADDRESSED_IN_ADR020_R2`: unconditional closed v3 and extensions. |

Repository-truth findings remain preserved without implementation verification: `RT-GOV-AUTO-WP01-F-001` partial platform/pilot proof; `RT-GOV-AUTO-WP01-F-002` not verified local lifecycle unavailable; `RT-GOV-AUTO-WP01-F-003` partial provider attestation; `RT-GOV-AUTO-WP01-F-004` partial platform configuration; `RT-GOV-AUTO-WP01-F-005` partial validator; `RT-GOV-AUTO-WP01-F-006` partial Drive IDs/permissions/readback; `RT-GOV-AUTO-WP01-F-007` partial provider recovery; `RT-GOV-AUTO-WP01-F-008` partial concurrency pilot.

Fresh review must test manual bootstrap/`DOCUMENTED_C`, no acceptance authority, App safety/literal ref, JCS cross-language/invalid JSON, frozen month-boundary retry, identical/conflicting concurrency, one reservation/successor, authoritative-history lookup, all 48 cells exactly once, one successor, blocked no continuation, restoration/rollback exclusion and rollback terminalization, mandatory nested closure/extensions, layer/member/pilot separation, no self-verification, history/compatibility/Drive boundaries, and no inference from unavailable evidence.

## 12. Consequences and next gate

Benefits: candidate immutability, deterministic member authority, bounded concurrency, explicit context trust, exact recovery, and lower routine operator involvement without critical-authority transfer. Costs: dedicated App, layered rulesets, event folding, adapters, exact-cardinality validation, disposable pilots, and unresolved local state.

Unverified later gates: actual rulesets/checks/bypass, App install/key, receipt pilots/API behavior, provider attestations/recovery, local worktrees/locks/processes, and Drive permissions/IDs. Rejected: candidate/Drive/comment-only receipts; push-recursive `GITHUB_TOKEN`; PR-mediated routine receipts; mutable external canonical DB; cohort-only authority; automatic activation; shared apply/rollback; one App-bypassable safety ruleset; informal JSON concatenation.

Implementation must validate GitHub refs, token behavior, workflow permissions, cumulative rulesets/available rules/rulesets API, and RFC 8785 JCS. Authenticated repository/runtime evidence remains authoritative.

If this exact R2 candidate passes fresh independent review, a separate operator decision may accept it and authorize rebaselined implementation planning. Review authorizes no later action.
