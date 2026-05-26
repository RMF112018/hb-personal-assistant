# 05 — Local Runtime Orchestration Specification

## Objective

Define the desired behavior for the upgraded morning runtime, including consent-aware Graph skipping, local source processing, action intelligence, Obsidian output, run ledger, and evidence.

## Target Command

```bash
hb-assistant run morning --dry-run --json
```

Optional apply mode may remain existing behavior if repo truth supports it:

```bash
hb-assistant run morning --json
```

## Stage Model

The orchestrator should emit a stage array with stable names and statuses.

| Stage | Purpose | Consent Required? |
|---|---|---:|
| `path_readiness` | Ensure app support, logs, DB, evidence, and auth dirs are usable. | No |
| `store_readiness` | Apply migrations and verify SQLite readiness. | No |
| `graph_auth_status` | Determine delegated status and blocker classification. | No live proof required |
| `graph_retrieval` | Retrieve new Graph data if delegated token and consent are available. | Yes |
| `local_signal_load` | Load existing source records, parser excerpts, calendar rows, body mentions. | No |
| `classification` | Run or reconcile local classification where applicable. | No |
| `action_extraction` | Extract/update action items from bounded signals. | No |
| `workstream_context` | Build source-linked context for brief/search. | No |
| `file_ingestion_preview` | Preview provenance-backed ingest candidates. | No for dry-run |
| `brief_generation` | Generate redacted source-linked brief content. | No |
| `obsidian_write` | Dry-run or write marker-bounded note. | No |
| `evidence_write` | Write sanitized evidence artifact. | No |
| `run_ledger_finish` | Mark run completed/skipped/error. | No |

## Stage Status Values

- `ok`
- `skipped_external_admin_consent`
- `skipped_no_token`
- `skipped_no_candidates`
- `blocked_local_path`
- `blocked_db_unavailable`
- `error_isolated`
- `completed_dry_run`
- `completed`

## JSON Output Contract

```json
{
  "implemented": true,
  "phase": 14,
  "run_id": 123,
  "dry_run": true,
  "status": "completed_dry_run",
  "blocker_classification": "EXTERNAL_ADMIN_CONSENT_BLOCKER",
  "stages": [
    {
      "stage": "graph_retrieval",
      "status": "skipped_external_admin_consent",
      "reason": "Delegated Graph consent pending",
      "counts": {}
    }
  ],
  "outputs": {
    "brief_generated": true,
    "obsidian_write_mode": "dry_run",
    "evidence_path": "~/Library/Application Support/HB Personal Assistant/evidence/...json"
  },
  "safety": {
    "m365_writeback": false,
    "full_email_bodies_persisted": false,
    "full_file_contents_persisted": false
  }
}
```

## Failure Isolation

A failure in one optional stage should not crash the whole run unless the stage is foundational:

Foundational blockers:

- paths unavailable;
- DB unavailable;
- schema migration failure;
- evidence directory unavailable.

Non-foundational isolated failures:

- Graph no-token or consent pending;
- no file candidates;
- one parser failure;
- one action candidate extraction failure;
- Ollama unavailable.

## Evidence Requirements

Each run should emit sanitized evidence under the configured evidence directory. The artifact should contain counts, statuses, source IDs, and redacted excerpts only.
