# 01 — N8C-2 Baseline & Carry-forward

## N8C-2 state (verified)
N8C-2 (Source/Card Identity Hardening) was committed locally in this session as **`319ceff0`**
(`feat(nas): add n8c source-card identity hardening`) on top of `c454a581`. Tree was clean; **not
pushed**. N8C-3 branches off `319ceff0`.

```
319ceff0  feat(nas): add n8c source-card identity hardening   <- N8C-3 base
c454a581  N8C-1 evidence: correct commit-state metadata
acd22926  N8C-1: neutral second-brain foundation
```

N8C-3 evidence lives in a NEW bundle `docs/evidence/nas-second-brain-n8c/20260705T205240Z/`, distinct
from N8C-2's `20260705T200705Z` and N8C-1's `20260705T185844Z` — N8C-2 and N8C-3 evidence are not
mixed.

## Carried-forward rules (preserved by N8C-3)
No schema migration (`LATEST_SCHEMA_VERSION` stays 99); no raw SQL / arbitrary filesystem exposure; no
raw/import DB mutation; `ai_outputs_card_upsert` remains the only sanctioned remote write; live `hb_*`
MCP tool names unchanged; source cards render byte-unchanged (`source_notes.py` untouched). N8C-3 adds
only read-only navigation surfaces. N8C-3 reuses the N8C-2 identity layer
(`source_card_identity.py`) and the N8C-2 read-only repo methods (`get_sources_for_note`,
`list_cards_for_source`) directly.

## Environment
Python venv shared across worktrees at `<repo>/.venv`. Tests run with
`PYTHONPATH=src:subrepos/construction-financial-review/src`.
