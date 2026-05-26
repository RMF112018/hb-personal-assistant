# 03 — Repo-Truth Audit Basis

## Objective

Record the repo-truth basis used to create this package. The local agent must revalidate these findings before patching.

## Current Known State From Prior Audit

| Area | Prior Finding | Implementation Implication |
|---|---|---|
| Repository | `RMF112018/hb-personal-assistant`, default branch `main`. | Work in the local repo and verify HEAD before edits. |
| Version | `1.3.0`. | Do not bump unless the repo's versioning convention requires it. |
| CLI | `auth`, `diagnostics`, `files`, `search`, `run`, `automation` are implemented; `vault`, `sync`, `actions`, `brief` were stubs at audit time. | Phase 14 should convert `actions` into a real group; optionally convert `brief` if repo truth supports. |
| Auth | Delegated MSAL provider exists; scope sanitizer exists. | Do not re-open reserved-scope defect unless it reproduces. |
| Token cache | Application Support token cache paths exist outside repo. | Preserve local-first state and strict permissions. |
| Graph | Central Graph client, mail, calendar, drive item clients exist. | Proof remains deferred until consent. |
| Store | SQLite schema includes source records, emails, events, files, parser outputs, action items, source links, runs, embeddings. | Use existing schema when possible; add migrations only when necessary. |
| Classification | Preview fast path and bounded full-body fallback exist. | Use classification results as action signals. |
| Files | Real ingest requires provenance-backed candidates and blocks missing provenance. | Do not reintroduce synthetic fallback into real ingest. |
| Retrieval | Parser excerpts are searchable; Ollama fallback exists. | Expand context, not necessarily embedding sophistication. |
| Obsidian | Marker-bounded writer exists; provenance link recording appears incomplete. | Implement `written_to_note` source links. |
| Automation | Morning orchestrator and launchd manager exist. | Upgrade from preview-like stages to complete local runtime. |
| Evidence | Stale DNS blocker language exists in README/architecture/final closeout. | Correct first. |

## Key Files To Inspect During Prompt 00

- `README.md`
- `pyproject.toml`
- `src/hb_assistant/cli/main.py`
- `src/hb_assistant/cli/auth.py`
- `src/hb_assistant/cli/diagnostics.py`
- `src/hb_assistant/cli/files.py`
- `src/hb_assistant/cli/search.py`
- `src/hb_assistant/cli/run.py`
- `src/hb_assistant/auth/`
- `src/hb_assistant/graph/`
- `src/hb_assistant/store/`
- `src/hb_assistant/links/`
- `src/hb_assistant/classification/`
- `src/hb_assistant/files/`
- `src/hb_assistant/retrieval/`
- `src/hb_assistant/obsidian/`
- `src/hb_assistant/automation/`
- `tests/`
- `docs/architecture/`
- `docs/decisions/`
- `docs/evidence/`

## Evidence Integrity Concern

Committed evidence and docs may still say DNS/network is the active blocker. Treat this as stale unless fresh command evidence proves current DNS failure. The current controlling implementation context says delegated login reaches Microsoft and admin consent remains pending.

## Required Revalidation Output

Before code patches, the local agent must create or update an evidence note with:

- branch;
- HEAD;
- local status;
- observed validation baseline;
- active blocker classification;
- stale doc references found;
- exact files to patch.
