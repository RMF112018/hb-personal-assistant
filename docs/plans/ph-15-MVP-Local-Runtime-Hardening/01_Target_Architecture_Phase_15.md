# 01 — Phase 15 Target Architecture

## Runtime Flow

```text
CLI / launchd
  -> hb-assistant run morning
    -> path readiness
    -> store readiness
    -> Graph auth status
       -> if no token / consent pending: classify blocker and continue local stages
    -> local signal load
    -> classification reconciliation
    -> action extraction
    -> workstream context build
    -> file ingestion preview
    -> brief generation
    -> Obsidian marker-bounded write or dry-run
    -> evidence write
    -> run ledger finish
```

## Core Components

| Component | Target Role |
|---|---|
| `cli/run.py` | Thin wrapper over `MorningRunOrchestrator` |
| `automation/orchestrator.py` | Single source of truth for stage model, blocker classification, local continuation |
| `actions/service.py` | Action extraction and optional persistence entry point |
| `actions/extractor.py` | Deterministic bounded-signal action candidate extraction |
| `store/repositories.py` | Idempotent persistence, source records, action items, source links, run ledger |
| `links/registry.py` | Provenance gate, action-aware links, `written_to_note` links |
| `retrieval/context.py` | Workstream context assembly, including mentions/actions/files/calendar/retrieval |
| `obsidian/writer.py` | Marker-bounded Obsidian writer and provenance behavior |
| `obsidian/brief.py` | Redacted daily brief content generation |
| `diagnostics` | Evidence, env, path, Graph status, sensitive scan |

## Design Principles

1. Truthful degradation: Graph consent blockers should not falsely fail local MVP operation.
2. Local-first: local store, fixture signals, and Obsidian output should prove value before live Graph.
3. Privacy-safe: no full bodies, full files, tokens, PEMs, secrets, or raw private content in evidence.
4. Idempotent: repeated runs should not duplicate actions, links, or Obsidian sections.
5. Source-linked: user-visible generated output should have traceable sources.
6. Operator-ready: Bobby should be able to run, inspect, and troubleshoot the assistant without reading code.

## MVP-Critical Contracts

### `hb-assistant actions extract --dry-run --json`

Must:

- return structured JSON;
- not persist action items;
- not persist source links;
- clearly disclose if it writes run ledger/evidence;
- bound and redact titles/excerpts;
- return deterministic stable keys.

### `hb-assistant run morning --dry-run --json`

Must:

- return full stage array;
- classify Graph blocker;
- continue local stages;
- generate brief content;
- dry-run Obsidian output;
- emit redacted evidence;
- not mutate Microsoft 365.

### Obsidian Writer

Must:

- touch only managed marker section;
- preserve user content outside markers;
- preserve checked task state where stable enough;
- record `written_to_note` provenance on apply path;
- not record note-write provenance on dry-run unless explicitly documented as evidence-only.
