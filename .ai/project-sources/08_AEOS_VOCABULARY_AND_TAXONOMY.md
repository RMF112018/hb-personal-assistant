---
standard: AEOS
version: "1.0"
status: normative
license: internal-use
---

# 08 — AEOS Vocabulary and Taxonomy

## 1. Purpose

This standard defines controlled AEOS terminology. Consistent vocabulary reduces ambiguity across planning, implementation, audit, and release decisions.

## 2. Core Terms

### Repository Truth

Current facts derived from direct inspection of repository files, history, branch state, tests, configuration, and documentation.

### Runtime Truth

Current facts derived from a running system, logs, API responses, database queries, monitoring, deployment receipts, or production behavior.

### Evidence

Specific, relevant, reproducible proof supporting a claim.

### Claim

A statement that something is true, implemented, tested, safe, complete, or ready.

### Acceptance Criterion

A stable, testable requirement used to judge whether work satisfies the objective.

### Finding

A reviewed defect, gap, risk, or unsupported claim requiring disposition.

### Trust Surface

A system boundary where trust is granted, withheld, degraded, or verified.

### Capability Surface

The set of actions a tool, service, model, or agent can perform.

### Approval Gate

A point where human authorization is required before proceeding.

### Evidence Package

A collected set of proof used for audit or Go/No-Go.

### Go/No-Go

A bounded decision about merge, deployment, production, or operational readiness.

### Canonical Memory

Durable, authoritative knowledge accepted into a repository, corpus, vault, or other governed knowledge base.

### Promotion

The act of moving information from draft, observation, or evidence into a more authoritative state.

### Receipt

A durable record that an action occurred, including identity, time, inputs, outputs, and status.

## 3. Workflow Terms

### Discovery

The phase that determines current state, unknowns, risks, and evidence needs.

### Architecture

The phase that defines target design, boundaries, invariants, alternatives, and acceptance criteria.

### Implementation Planning

The phase that converts architecture into executable agent instructions.

### Plan Review

The phase that evaluates an implementation plan before execution.

### Implementation Audit

The phase that evaluates completed implementation against criteria and evidence.

### Corrective Review

The phase that verifies remediation of findings.

### Production Readiness

The phase that determines release and operational safety.

## 4. Status Values

### Acceptance Criterion Status

- PASS
- PARTIAL
- FAIL
- NOT VERIFIED
- NOT APPLICABLE

### Finding Status

- OPEN
- FIX CLAIMED
- VERIFIED FIXED
- DEFERRED WITH ACCEPTED RISK
- REJECTED WITH RATIONALE
- NOT REPRODUCIBLE

### Go/No-Go Decision

- GO
- CONDITIONAL GO
- NO-GO
- INSUFFICIENT EVIDENCE

## 5. Severity Taxonomy

### Critical

Likely severe production outage, destructive behavior, data loss, or security compromise.

### High

Material correctness, safety, migration, or trust-boundary failure.

### Medium

Important reliability, maintainability, or completeness issue.

### Low

Minor defect or documentation/cleanup issue.

### Informational

Observation without immediate defect classification.

## 6. Generalization Taxonomy

When deriving AEOS patterns from repositories, classify as:

- AEOS Core
- AEOS Optional Profile
- Reference Implementation Only
- Do Not Generalize
- Needs More Evidence

## 7. Source Authority Taxonomy

- Runtime evidence
- Repository evidence
- Approved specification
- Repository-local governance
- AEOS standard
- Session instruction
- Prior conversation
- Memory/general knowledge

## 8. Artifact Taxonomy

- Repository-truth report
- Architecture artifact
- ADR
- Implementation plan
- Local-agent handoff
- Implementation report
- Evidence package
- Audit report
- Corrective review
- Production-readiness report
- Go/No-Go record
- Pattern candidate

## 9. Normative Usage Rules

- Use "repository truth" only when based on inspected repository evidence.
- Use "runtime truth" only when based on running-system evidence.
- Use "claim" for agent statements not yet verified.
- Use "finding" only for reviewed issues with stable identifiers.
- Use "GO" only for bounded decisions and never as general praise.
- Use "production-ready" only after production-readiness gates are satisfied.
