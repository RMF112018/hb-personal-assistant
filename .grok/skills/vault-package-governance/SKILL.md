# Vault Package Governance Skill

Use this skill when planning/package governance is involved for HB Personal Assistant.

## Purpose
Maintain consistent lifecycle management between repo and vault package records while preserving repo-truth precedence.

## Required Workflow
1. Verify lifecycle prerequisites from repo evidence and migration manifests.
2. Confirm package classification against current `Package Registry.md`.
3. Ensure closed packages have `CLOSURE_NOTE.md` and resolved closure status.
4. Keep `docs/evidence/**` in-repo and referenced only.
5. Block cleanup actions if manifest coverage/hash/metadata gates fail.

## Rules
- Do not re-copy package payloads back into repo once vault is canonical.
- Do not classify evidence bundles as lifecycle packages.
- Update registry and manifest flags together to avoid drift.
- Preserve no-secret and no-plugin governance standards.
