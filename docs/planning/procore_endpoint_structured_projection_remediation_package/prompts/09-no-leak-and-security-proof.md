# 09 — No-Leak and Security Proof

## Goal

Prove the remediation did not commit or emit sensitive data.

## Required checks

- `git diff --name-only origin/main...HEAD`
- no `.sqlite`, `.db`, `.payload`, raw `.json`, `.env`, `.pyc`, `__pycache__` staged
- no raw payload bodies in docs/evidence
- no signed URLs
- no bearer/access/refresh tokens
- no Procore auth secrets
- no model prompt containing raw payload body

## Required evidence

Write:

`docs/evidence/procore_endpoint_structured_projection_remediation/08-no-leak-scan.md`

Classify any detector hits as:
- detector literal,
- code constant,
- redacted example,
- false positive,
- real leak.

A real leak is a stop condition and must be removed before commit.
