# 01 — Target Architecture and Closed Decisions

## Objective

Define the target architecture for Phase 14 of the HB Personal Assistant, grounded in current repo truth and designed to advance the system without waiting for Microsoft delegated Graph consent.

## Phase 14 Architecture Summary

Phase 14 converts the project from a set of strong local-first components into a cohesive local runtime assistant loop:

```text
Local/Graph source metadata -> source_records -> classification/signals -> action extraction -> source-linked context -> Obsidian output -> run ledger/evidence
```

Where Graph consent is unavailable, the system must still run against local deterministic fixtures and previously persisted source records.

## Architectural Components

### 1. CLI Shell

Existing CLI groups:

- `auth`
- `diagnostics`
- `files`
- `search`
- `run`
- `automation`

Phase 14 adds or upgrades:

- `actions extract --dry-run --json`
- `actions list --json`
- `actions reconcile --dry-run --json`
- `brief generate --dry-run --json` if repo truth supports converting the current stub into a real command group.

### 2. Source Records and Store

The SQLite store remains the local source of truth for persisted metadata, provenance, action records, parser excerpts, run ledger, and local retrieval data. No full email bodies or file contents are stored.

### 3. Signal Layer

Inputs include:

- redacted email metadata;
- body preview flags;
- bounded body mention flags/excerpts;
- calendar metadata;
- file metadata;
- parser excerpts;
- retrieval hits;
- existing source links.

### 4. Action / Work Product Intelligence Layer

This layer creates stable, source-linked action records from bounded signals. It should identify:

- direct action requested from Bobby;
- Bobby mentioned but not directly assigned;
- waiting-on-someone-else signals;
- review/approval/response/follow-up needs;
- meeting prep actions;
- file review actions.

### 5. Workstream Context Layer

The context layer assembles a concise current workstream model for brief generation and interactive retrieval. It must include source IDs and link metadata for traceability.

### 6. Obsidian Output Layer

The Obsidian writer remains marker-bounded and frontmatter-safe. Phase 14 must implement `written_to_note` provenance links and ensure generated notes can be traced back to the source records/actions used.

### 7. Morning Orchestration Layer

The morning run must become a reliable local workflow:

1. initialize paths/store;
2. classify external-blocked Graph stages when consent is unavailable;
3. build local workstream context;
4. extract/reconcile actions;
5. generate brief content;
6. dry-run or write Obsidian output;
7. record run ledger;
8. emit sanitized evidence.

## Closed Decisions

| ID | Decision | Rationale |
|---|---|---|
| D-P14-001 | Continue development while admin consent is pending. | Local deterministic work can proceed safely. |
| D-P14-002 | Treat admin consent as external blocker, not code failure. | Latest context says login reaches Microsoft. |
| D-P14-003 | Correct stale DNS blocker documentation first. | Evidence must be trustworthy before more implementation. |
| D-P14-004 | Action records require stable keys. | Prevent duplicate tasks across repeated runs. |
| D-P14-005 | Every action record should have at least one source link. | Enables traceability and auditability. |
| D-P14-006 | Action extraction is deterministic-first. | Core acceptance must not require LLM/Ollama. |
| D-P14-007 | Local models remain optional. | Ollama should enhance ranking/synthesis but not block runs. |
| D-P14-008 | Obsidian writes are marker-bounded. | Protects Bobby's manual notes. |
| D-P14-009 | Generated output must include source IDs or source map. | Supports verification and correction. |
| D-P14-010 | CI must not require Microsoft 365 credentials. | Public repo/local test safety. |

## Boundary Conditions

The local agent may add deterministic fixtures, tests, CLI commands, schema migrations, and docs. The local agent may not add cloud services, Graph write paths, full-content persistence, or tenant-specific secret assumptions.
