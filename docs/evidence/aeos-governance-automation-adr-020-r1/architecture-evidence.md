---
title: "ADR-020 Architecture Evidence — AEOS Standing Policy and Receipt Control Plane"
artifact_id: "EVIDENCE-AEOS-GOVERNANCE-AUTOMATION-ADR-020-R1"
classification: "Evidence"
artifact_type: "Architecture Evidence"
version: "1.0"
status: "Candidate — Pending Independent Architecture Review"
date: "2026-07-22"
repository: "RMF112018/hb-personal-assistant"
branch: "arch/adr-020-aeos-governance-automation-r1"
base_sha: "b2b7bb63443bf5a098c2851eb101e4d5c148c589"
evidence_parent_sha: "3ed085800163c7dbb3601d7e29e41d4dea89816a"
candidate_head_authority: "authenticated GitHub branch tip after the architecture commit"
authorization_id: "AUTH-AEOS-GOV-AUTOMATION-WP-GOV-02-ADR-020-20260722-01"
---

# ADR-020 Architecture Evidence

## 1. Bounded disposition

`WP-GOV-02` architecture authoring is complete at the candidate-content level and is ready for a fresh independent architecture review after the final branch commit is authenticated.

This evidence does not approve ADR-020 and does not authorize implementation or any later action.

## 2. Exact governing inputs

| Input | Identity | SHA-256 | Verification |
|---|---|---|---|
| Approved plan | `PLAN-AEOS-GOVERNANCE-AUTOMATION-AMENDMENT-001-R6` | `0cc105b375f09bb5df712a13488dcaa07375520315f2b1dc708409eaf6421dd6` | Exact local source bytes verified |
| Qualifying plan review | `REVIEW-PLAN-AEOS-GOVERNANCE-AUTOMATION-AMENDMENT-R6-20260722-01` | `2a6f92adeeb3a7aa947ba1ed6582b998b1e2ae61dafee03770953d5a9d49223b` | Exact local source bytes verified |
| Repository-truth report | `AUDIT-AEOS-GOVERNANCE-AUTOMATION-WP-GOV-01-REPOSITORY-TRUTH-R1` | `ace76048c940151fca5640bb561d2f6a497824c133a097b57b5e0fb322c6ca5c` | Exact local source bytes verified |
| Repository-truth checkpoint | `CP-AEOS-GOVERNANCE-AUTOMATION-WP-GOV-01-REPOSITORY-TRUTH-R1` | `08f3cf20b8142ef2d86d137a626591191615df72b6a9ecd6cb8064f486375b02` | Exact local source bytes verified |

All four byte-bearing inputs had terminal newlines and matched their authorization bindings.

## 3. Repository and branch preflight

| Field | Observed value |
|---|---|
| Repository | `RMF112018/hb-personal-assistant` |
| Visibility | Public |
| Default branch | `main` |
| Authorized base | `b2b7bb63443bf5a098c2851eb101e4d5c148c589` |
| Current `main` at preflight | `b2b7bb63443bf5a098c2851eb101e4d5c148c589` |
| Base comparison | `identical`; ahead `0`; behind `0` |
| Open pull requests | None returned |
| Target branch before creation | No matching branch returned |
| Created branch | `arch/adr-020-aeos-governance-automation-r1` |
| Registration commit | `3ed085800163c7dbb3601d7e29e41d4dea89816a` |
| Worktree mode | `remote_only` |
| Pull request | Not created; not authorized |

The branch was created from the exact base and registered before substantive ADR authoring.

## 4. Governing repository source identities

The architecture was checked against the following exact files at the authorized base:

| Path | Git blob SHA |
|---|---|
| `AGENTS.md` | `ba21e438f62216f9d5a3961ea6b2ec5b23a57c19` |
| `AI_OPERATING_MANUAL.md` | `395c09bb6631744f2b3667f541f83a05fba15c72` |
| `.ai/project-sources/00_AEOS_MASTER_INDEX.md` | `b6e0a027bd2a8599be6dd1d749c7e6214a4a3b52` |
| `.ai/project-sources/01_AEOS_OPERATING_MANUAL.md` | `bd72610e3d55b62fc067a8c0d316a7f66e9133e7` |
| `.ai/project-sources/02_AEOS_WORKFLOW_STANDARD.md` | `04eb0b5d4fb93887b5d4fe4777e55f99871e9a9b` |
| `.ai/project-sources/04_AEOS_EVIDENCE_AND_TRUST_STANDARD.md` | `1e5021309e789c887756ae75e988240ff4c92602` |
| `.ai/project-sources/07_AEOS_LOCAL_AGENT_OPERATING_CONTRACT.md` | `c9f42eaf24558eac87fa65773c3ef4b793591eb4` |
| `docs/decisions/ADR-019-github-first-engineering-control-plane.md` | `4b10ac73b49665938b4d7cd1c842ec7dee4293f7` |
| `docs/governance/branch-worktree-lifecycle-policy.md` | `0c404f3a172a9c30be36067fcb6bbaacecc723e1` |
| `docs/implementation-plans/github-first-control-plane-migration.md` | `f2d4279f29c7e4b796510a25a2d01f4c137237fb` |
| `.ai/schemas/goal-loop/checkpoint-request.schema.json` | `eba5b5673ca7ef92139d3a5880f6b7509e38118a` |
| `.ai/schemas/goal-loop/external-review.schema.json` | `fa7f005a0bbee08fd35da61d6165358604f0e08f` |
| `.ai/schemas/goal-loop/state.schema.json` | `77d9736d1b830ca57db6a7f17f0ccb278c830b45` |
| `.ai/schemas/goal-loop/authorization.schema.json` | `07455a58f95ba7a8623990bf546067ecf8661265` |
| `.ai/aeos/bin/validate_goal_loop_contracts.py` | `07799b82190090069d7494bdfea0937f682e5aa8` |
| `.github/workflows/aeos-governance-validation.yml` | `f6635ba8fcb7340ff0584bd6366dafce1ac3a9ee` |

## 5. Repository-truth constraints carried into ADR-020

| Finding | Architectural treatment |
|---|---|
| `RT-GOV-AUTO-WP01-F-001` | Dedicated App issuer, same-run append verification, explicit receipt ruleset/bootstrap order, freeze and operator recovery. |
| `RT-GOV-AUTO-WP01-F-002` | Existing lifecycle records imported as claims; local truth required; absent branch results do not prove cleanup; preservation-first. |
| `RT-GOV-AUTO-WP01-F-003` | Controller-issued context attestation, evidence tiers, immutable log references, one-time nonce, no self-upgrade. |
| `RT-GOV-AUTO-WP01-F-004` | Direct ruleset/configuration export, exact desired-state diff, independent validation, separate restoration/rollback authority. |
| `RT-GOV-AUTO-WP01-F-005` | Explicit three-way authorization/state/authenticated-head comparison and required negative fixture. |
| `RT-GOV-AUTO-WP01-F-006` | AEOS package-local Drive `policies/` folder and direct child index selected for later publication. |
| `RT-GOV-AUTO-WP01-F-007` | Provider adapter separation, disposable target, preflight, distinct planned restoration and failure rollback. |
| `RT-GOV-AUTO-WP01-F-008` | Expected-parent non-force CAS, canonical idempotency key, five attempts, exact blob/ancestry readback, pilot proof. |

No finding is marked independently verified fixed by this authoring context.

## 6. Selected architecture decisions

1. Static policy and schema definitions remain on reviewed `main`.
2. Dynamic governance facts are immutable events on `aeos/receipts`.
3. The routine writer is a dedicated least-privilege GitHub App installation.
4. The controller uses same-run validate → append → readback verification.
5. Receipt branch updates use `force: false` and exact-parent optimistic CAS.
6. One event path and payload identity is authoritative; catalogs are derived.
7. Authorization consumption is reserved by receipt before the external action starts.
8. Context eligibility uses trusted provider attestations; model self-assertion alone is not standing-policy evidence.
9. Policy state is an event fold over exact versioned policy/mapping/manifests.
10. Cohort state never substitutes for exact member `ACTIVE`.
11. Configuration apply, validation, planned restoration, restoration validation, failure rollback, and rollback assessment remain distinct.
12. Drive policy publication is package-local and non-authorizing.

## 7. Platform mechanics checked

Current GitHub documentation was consulted for:

- non-force Git reference updates and fast-forward protection;
- `GITHUB_TOKEN` workflow-trigger suppression and dispatch exceptions;
- per-workflow token permissions;
- ruleset bypass actors, including GitHub Apps;
- repository ruleset API representations.

Architecture consequence:

- receipt persistence cannot depend on a `GITHUB_TOKEN`-authored push creating a second workflow run;
- receipt updates must be non-force;
- the App/ruleset permission model requires later direct export and an operator-authorized credential/configuration lifecycle;
- authenticated repository settings, not documentation, remain authoritative for actual behavior.

## 8. ADR-020 source identity

| Field | Value |
|---|---|
| Path | `docs/decisions/ADR-020-aeos-standing-policy-and-receipt-control-plane.md` |
| Representation | UTF-8 raw Markdown |
| Hash scope | `source_bytes` |
| SHA-256 | `3d4930c5642b2a7df1ffdf1bf29028c184c5a8f741ed51246691a91938b6c372` |
| Byte count | `51452` |
| Line count | `1177` |
| Terminal newline | Present |

## 9. Focused non-mutating validation

The candidate source was checked for:

- all `AC-GOV-001` through `AC-GOV-025`;
- all `RT-GOV-AUTO-WP01-F-001` through `-008`;
- explicit authority and non-authority boundaries;
- selected receipt issuer and permissions;
- same-run verification and no push-recursion dependency;
- exact CAS, idempotency, contention, readback, freeze, and recovery;
- six-layer separation;
- policy/member/cohort/pilot/configuration lifecycle preservation;
- v1/v2/v3 compatibility;
- Drive nearest-owner topology;
- balanced Markdown code fences;
- absence of unresolved issuance placeholders;
- no implementation code or configuration mutation.

Result:

```text
missing acceptance criteria: 0
missing repository-truth findings: 0
unresolved placeholder sentinels: 0
Markdown code-fence count: 42 (balanced)
ADR source SHA-256: 3d4930c5642b2a7df1ffdf1bf29028c184c5a8f741ed51246691a91938b6c372
```

Repository validators and tests were not executed because no local checkout exists and this architecture package changes no implementation/schema/workflow files. Implementation validation remains a later work package.

## 10. Scope and mutation ledger

Authorized and performed:

- created exact remote architecture branch;
- committed branch registration;
- authored ADR-020 candidate;
- authored architecture-only evidence;
- prepared an external exact-head architecture review request.

Not performed:

- PR creation;
- review submission;
- implementation;
- schema, validator, workflow, policy, mapping, manifest, ruleset, check, receipt, credential, configuration, runtime, or Drive mutation;
- merge, cleanup, deployment, production activation, or risk acceptance.

## 11. Limitations

- Rulesets, branch protection, required checks, bypass actors, auto-delete settings, and workflow default permissions remain `NOT VERIFIED`.
- Local branches, worktrees, dirty state, locks, and process use remain `UNAVAILABLE`.
- Dedicated App installation and credential storage are not proven.
- Receipt CAS is architecturally specified but not proven by repository pilot evidence.
- Provider-native context attestations are not implemented.
- Safe disposable configuration targets and rollback APIs are not proven.
- Drive permissions and new child IDs do not exist yet.
- No runtime behavior is claimed.

## 12. Review boundary

The independent reviewer must bind to the exact final branch head authenticated after the architecture commit. A later commit invalidates the review.

Architecture approval does not authorize implementation. The next state remains operator-gated implementation planning after architecture acceptance.
