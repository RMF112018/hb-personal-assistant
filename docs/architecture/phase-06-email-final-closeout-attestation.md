# Phase 06 Final Closeout Attestation Model (Prompt 14)

## Purpose

Define final attestation rules for Phase 06 operational email workflows.

## Attestation Tiers

1. Structural/Repository Attestation
- command chain exists
- read-only guardrails and mutation lockout exist
- encrypted body storage design is enforced
- plaintext-leakage protections exist

2. Runtime Environment Attestation
- requires live endpoint reachability and local app DB availability
- executes operational command matrix and captures safe receipts

## Conditional vs Full Operational Verdict

- Conditional operational verdict:
  repository truth + tests + sanitized runtime-attempt receipts pass, but live environment prerequisites are unavailable.

- Full operational verdict:
  all runtime matrix commands execute successfully in a live-local environment with valid auth and data access.

## Evidence Requirements

Prompt 14 closeout must include:
- no mailbox mutation proof
- no plaintext body leakage proof
- encrypted body storage closeout proof
- final validation closeout report with command matrix and known deferrals

## Prompt 15 Operator Handoff Boundary

Prompt 15 establishes the operator-facing execution boundary for Phase 06:
- day-to-day and dry-run command procedures are centralized in `docs/runbooks/phase-06-operational-email-workflows.md`;
- controlled decrypt-read usage is documented with explicit plaintext-handling constraints;
- handoff status and validation outcomes are captured in `docs/evidence/construction-intelligence-phase-06-email/15-operator-runbook-and-handoff.md`.

This does not expand Phase 06 scope or mutate API behavior; it formalizes operational usage and maintenance guardrails for Bobby and future local agents.
