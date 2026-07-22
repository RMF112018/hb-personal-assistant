---
title: "ADR-020 R2 Architecture Evidence — AEOS Standing Policy and Receipt Control Plane"
artifact_id: "EVIDENCE-AEOS-GOVERNANCE-AUTOMATION-ADR-020-R2"
classification: "Evidence"
artifact_type: "Corrective Architecture Evidence"
version: "2.0"
status: "Candidate — Pending Fresh Independent Architecture Review"
date: "2026-07-22"
repository: "RMF112018/hb-personal-assistant"
branch: "arch/adr-020-aeos-governance-automation-r1"
base_sha: "b2b7bb63443bf5a098c2851eb101e4d5c148c589"
reviewed_r1_head: "a6f7b21521283824709cbcfb8ee828bdd9703dcc"
corrective_adr_commit: "235b8c269f6e7c62c5814939803a8424d3dfe75a"
authorization_id: "AUTH-AEOS-GOV-AUTOMATION-WP-GOV-02-ADR-020-R2-20260722-01"
---

# ADR-020 R2 Corrective Architecture Evidence

## 1. Disposition and authority boundary

`WP-GOV-02` corrective architecture authoring is complete at the ADR-content level. This evidence claims only `ADDRESSED_IN_ADR020_R2`; it does not independently mark findings fixed, accept ADR-020, authorize implementation, or authorize any App, credential, receipt branch, ruleset, check, policy, pilot, configuration, Drive, merge, cleanup, deployment, production, or risk action.

## 2. Exact bindings and preflight

| Item | Exact identity |
|---|---|
| Approved plan | `PLAN-AEOS-GOVERNANCE-AUTOMATION-AMENDMENT-001-R6` / `0cc105b375f09bb5df712a13488dcaa07375520315f2b1dc708409eaf6421dd6` |
| Controlling R1 review | `REVIEW-ADR-020-AEOS-STANDING-POLICY-R1-20260722-01` / `a2dce8a18a19dcb69fcb05d95b3fbefade2c37259e783172ab31525a62ff8d35` / `REVISE` |
| Required starting head | `a6f7b21521283824709cbcfb8ee828bdd9703dcc` |
| Starting branch result | exact match before first corrective commit |
| Base and `main` | `b2b7bb63443bf5a098c2851eb101e4d5c148c589`; identical at preflight |
| Pull request | none created; not authorized |

The original ADR source hash `3d4930c5642b2a7df1ffdf1bf29028c184c5a8f741ed51246691a91938b6c372` and blob `7d37fd50f250919127c351aa2fa1a71281656e43` matched the authorization before correction.

## 3. ADR-020 R2 source identity

| Field | Value |
|---|---|
| Path | `docs/decisions/ADR-020-aeos-standing-policy-and-receipt-control-plane.md` |
| Version | `0.2` |
| Representation | UTF-8 raw Markdown |
| Hash scope | `source_bytes` |
| SHA-256 | `49a0b334cd4f09eb6212a7e5119eeaf9f0f480ba35a6312ee732a802647640d9` |
| Git blob SHA | `4c3c1e3bbc273293efbd9e197bc12b76e46af7ab` |
| Byte count | `21970` |
| Line count | `230` |
| Terminal newline | present |
| Corrective ADR commit | `235b8c269f6e7c62c5814939803a8424d3dfe75a` |

## 4. Finding-by-finding architecture treatment

| Finding | R2 treatment and required independent closure test |
|---|---|
| `ARCH-AEOS-GOV-AUTO-ADR020-R1-F-001` | Adds `ACCEPTED_BY_OPERATOR`, exact review/head binding, source-byte bootstrap decision, later import, manual `DOCUMENTED_C` acceptance without auto eligibility, route conflict suspension, and zero action authority. Test first-policy bootstrap, valid manual acceptance, automatic rejection for `DOCUMENTED_C`, invalid/stale rejection, and no implementation authority. |
| `ARCH-AEOS-GOV-AUTO-ADR020-R1-F-002` | Splits non-bypassable `AEOS-RECEIPT-HISTORY-SAFETY` from App-bypassable writer restriction; fixes literal repo/install/ref; prohibits caller-selected refs. Test App fast-forward append and rejection of delete, force, rewind, non-fast-forward, safety bypass, and alternate refs. |
| `ARCH-AEOS-GOV-AUTO-ADR020-R1-F-003` | Adopts RFC 8785 JCS, closed I-JSON input, versioned domain separator, uint64 length delimiter, frozen event bytes/path/time/scope before attempt one, authoritative-history idempotency, conflicting-scope suspension, and at-most-one reservation/successor. Test cross-language canonicalization, invalid JSON, month-boundary retry, identical/conflicting concurrency, replay, second reservation, and exact-one successor. |
| `ARCH-AEOS-GOV-AUTO-ADR020-R1-F-004` | Defines closed modes/outcomes/evidence, 12 exact routes, and normative 8×6 matrix covering all 48 tuples. Test one classification and successor per tuple, invalid-before-apply, blocked no continuation, planned restoration/rollback exclusion, unsafe suspension, and `ABORTED_ROLLED_BACK`. |
| `ARCH-AEOS-GOV-AUTO-ADR020-R1-F-005` | Makes `additionalProperties:false` unconditional for every authoritative v3 and nested authority-bearing object; permits only closed/versioned/hash-defined extensions with reviewed authority effects. Test unknown top-level, nested, enum, context, receipt, policy, pilot, recovery, and extension failures. |

No finding is marked `VERIFIED_FIXED` by this session.

## 5. Acceptance and repository-truth reconciliation

All `AC-GOV-001` through `AC-GOV-025` appear in the ADR and were checked for continued separation of review validity, operator/standing acceptance, policy eligibility, authorization, handoff, exact-head binding, one-action authority, recovery, compatibility, and publication boundaries.

Repository-truth findings remain evidence-gated rather than upgraded: `RT-GOV-AUTO-WP01-F-001` partial; `RT-GOV-AUTO-WP01-F-002` not verified; `RT-GOV-AUTO-WP01-F-003` through `-008` partial. Actual rulesets, App installation, credential storage, receipt concurrency, provider attestation/recovery, local worktree/process state, and Drive IDs/permissions remain later-gate evidence.

## 6. Focused non-mutating validation

Local source validation confirmed:

```text
missing AC-GOV-001..025: 0
missing ARCH R1 findings F-001..005: 0
missing RT findings F-001..008: 0
Markdown code fences: balanced
terminal newline: present
ADR SHA-256: 49a0b334cd4f09eb6212a7e5119eeaf9f0f480ba35a6312ee732a802647640d9
ADR Git blob: 4c3c1e3bbc273293efbd9e197bc12b76e46af7ab
```

The architecture review must independently evaluate the substantive correctness of the two-layer ruleset model, RFC 8785 envelope, global idempotency, 48-tuple matrix, and schema closure. Repository implementation and product suites were not run because the authorized diff is architecture documentation only.

## 7. Mutation and limitation ledger

Performed under authorization: revised ADR-020 on the existing registered branch; updated architecture evidence and lifecycle registration; prepared a true-file review request and checksum sidecar.

Not performed: implementation, PR/review/issue/comment/check creation, App or credential work, receipt branch or receipt, ruleset/branch protection/required-check/configuration change, policy activation, pilot, Drive mutation, merge, cleanup, deployment, production, or risk acceptance.

Limitations remain: platform settings and App behavior are not proven; local worktree state is unavailable; no runtime behavior is claimed. Final candidate head is resolved from authenticated GitHub after the registration commit; any later commit invalidates review.
