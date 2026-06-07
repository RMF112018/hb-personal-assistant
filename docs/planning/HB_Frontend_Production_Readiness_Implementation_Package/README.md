# HB Frontend Production Readiness Implementation Package

Generated: 2026-06-07T07:23:55.448328+00:00

Repository: `RMF112018/hb-personal-assistant`  
Target branch: `main`  
Audit HEAD used as package baseline: `be470af1326c82b4c78be6103969e6a0622067be`  
Latest relevant FastAPI/frontend commit reviewed in audit: `4d902ce0ffb88e4e2e0eb362f7059cba0ff4928a`

This package converts the frontend production-readiness audit into an implementation-ready handoff for a local coding agent. It is designed to be applied in sequence after a fresh repo-truth rebaseline. The package itself does not modify source code.

## Use Order

1. Read `00_PACKAGE_MANIFEST.md`.
2. Read `01_MASTER_AGENT_INSTRUCTIONS.md`.
3. Run the preflight in `02_REPO_TRUTH_PREFLIGHT.md`.
4. Execute prompts in numeric order under `prompts/`.
5. After each prompt, write evidence under `docs/evidence/frontend-production-readiness-implementation/` in the local repository.
6. Do not start Prompt 17 until Prompt 16 has green validation or an explicitly documented exception.

## Primary Objective

Make the FastAPI / Vite React analytics dashboard fully operational, polished, stable, and production-ready for local-first construction management use while preserving the current safety posture:

- no active in-app chat;
- no source-system writeback;
- no live sync from setup flows;
- no raw email body, document text, prompts/responses, tokens, secrets, signed URLs, download URLs, or PEM material serialized to UI or evidence;
- admin-only governance stays admin-only;
- normal operator workflow remains construction-management-first and low-friction.
