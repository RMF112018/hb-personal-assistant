# 01 — N8C-3 Baseline & Carry-forward

## Commit lineage (all local-only, not pushed)
```
<N8C-4 branch head>  (uncommitted)  ops/nas-second-brain-n8c-04-claim-extraction-20260705T215143Z
86701ad8  feat(nas): add n8c read navigation surfaces          <- N8C-4 base
319ceff0  feat(nas): add n8c source-card identity hardening    (N8C-2)
c454a581  N8C-1 evidence: correct commit-state metadata        (N8C-1 corrected base)
```
- N8C-1 corrected base: `c454a581`
- N8C-2 commit: `319ceff0`
- N8C-3 commit: `86701ad8`
- N8C-4 branch: `ops/nas-second-brain-n8c-04-claim-extraction-20260705T215143Z`, base `86701ad8`.

N8C-4 evidence is a NEW bundle `docs/evidence/nas-second-brain-n8c/20260705T215143Z/`, distinct from
N8C-1/N8C-2/N8C-3.

## Builds on
- **N8C-2** (`source_card_identity`): `get_source_for_card` (ambiguity), `classify_card_state`
  (current/stale/missing/duplicate/source_deleted/no_card), `get_card_for_source`.
- **N8C-3** (`source_navigation`): `get_source` (bounded source content) is the extraction input; the
  claim-read API mirrors the N8C-3 `/api/assistant/*` closure pattern.

## Carried-forward rules (preserved)
N8C-3 navigation + intentional bounded-deep-content default intact; `ai_outputs_card_upsert` remains
the only sanctioned remote write; raw SQL/shell/filesystem denied; no `db_allowlist` expansion; remote
MCP `assistant_*` surface unchanged at 12 tools (no claim tool added remotely). N8C-4 adds one schema
version (99→100) for the claim tables only.

## Environment
Shared venv at `<repo>/.venv`; tests via `PYTHONPATH=src:subrepos/construction-financial-review/src`.
