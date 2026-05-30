# 15 — Source-Linked Retrieval Proof (Phase 06A)

**Prompt:** Prompt 14 — Source-Linked Retrieval Proof · **Date:** 2026-05-30
**Posture:** Offline (SQLite only); no Graph; no embeddings/Ollama; no writeback. Read-only.
No new migration (schema stays at version 19).

## What changed

- **`src/hb_assistant/construction/graph/file_retrieval.py`** (new) — `FileRetriever` performs
  **deterministic, offline** keyword retrieval over the bounded redacted parser excerpts in V19
  `construction_file_extraction_runs` (`text_excerpt_redacted`, Prompt 11). It reuses the scoring
  pattern from `retrieval/retriever.py` (query-term overlap + exact-phrase boost, capped at 1.0)
  against the construction store — no embeddings, no Graph — so results are fully reproducible.
- **`hb-assistant graph files retrieve`** — `--query` (required), `--project`/`--source` (optional),
  `--limit`, `--json`. Matches the Prompt 17 validation-matrix command.

## Source traceability (result contract)

Each hit links the parser output back to its source. Returned fields:

| Field | Source |
| --- | --- |
| `source_id`, `drive_id`, `drive_item_id` | drive item identity (`get_drive_item`) |
| `name_redacted` | drive item name (bounded + PII-masked) |
| `web_url` | SharePoint/OneDrive item URL (plain item link; never a signed/download URL) |
| `project_key` | project identity (extraction run / source) |
| `excerpt_redacted` | bounded redacted parser excerpt (≤2000 chars; emails/phones/tokens masked) |
| `parser_output_id` | the extraction run id (`extraction_id`) |
| `processing_receipt_id` | the controlled-download receipt id (`construction_graph_download_receipts`) |
| `content_hash`, `parser_name`, `char_count`, `created_utc`, `score` | provenance / ranking |

## Deterministic retrieval proof (seeded; offline)

Seed: a matching, eligible, extracted RFI doc (`rfi1`) in `tropical` with a download receipt; a
non-matching extracted doc; and a `review_required` extracted doc (`sens1`). Query:
`"RFI submittal meeting minutes"`, scope `--project tropical`.

```json
{
  "command": "graph files retrieve",
  "query": "RFI submittal meeting minutes",
  "ok": true,
  "result": {
    "project_key": "tropical",
    "hit_count": 1,
    "candidates_considered": 2,
    "review_routed_excluded": 1,
    "hits": [
      {
        "source_id": "sp_2023projects_23_435_01_tropical_sl",
        "project_key": "tropical",
        "drive_id": "D1",
        "drive_item_id": "rfi1",
        "name_redacted": "RFI-012 Submittal.pdf",
        "web_url": "https://hedrickbrothers.sharepoint.com/sites/tropical/RFI-012.pdf",
        "parent_path": "/RFIs",
        "excerpt_redacted": "RFI-012 submittal review: meeting minutes note the structural shop drawings are due. Contact [email-redacted] regarding the [token-redacted] approval.",
        "score": 1.0,
        "parser_output_id": "ext1",
        "processing_receipt_id": "rcpt1",
        "content_hash": "h1",
        "char_count": 150
      }
    ],
    "guardrails": {
      "external_systems": "read_only",
      "writeback": "none",
      "graph_calls": "none",
      "full_text_persisted": false,
      "excerpt_bounded_redacted": true,
      "source_linked": true,
      "review_routed_excluded": true,
      "permission_tightening": "deferred"
    }
  }
}
```

### Rendered result table

| Score | Project | File | Excerpt | Source |
|---:|---|---|---|---|
| 1.00 | tropical | RFI-012 Submittal.pdf | RFI-012 submittal review: meeting minutes … [email-redacted] … [token-redacted] … | drive_item `rfi1` · `web_url` · parser `ext1` · receipt `rcpt1` |

_All excerpts are bounded and redacted. Full source document text is not rendered._

## Bounded excerpts only

- Retrieval reads the already-bounded, already-redacted `text_excerpt_redacted` (≤2000 chars; V19
  CHECK `full_text_persisted = 0`) and re-applies `_bounded_redact` defensively. The seeded
  `[email-redacted]` / `[token-redacted]` markers survive; no raw email/token/full-document text is
  returned. `name_redacted` is bounded + PII-masked.

## Review routing is never bypassed

- Any extraction run flagged `review_required = True` is excluded, and any drive item present in the
  **open review queue** (Prompt 12 routing) is excluded. In the proof, `sens1` (`review_required`) is
  dropped → `review_routed_excluded: 1`, `hit_count: 1`. Review-routed / sensitive files are never
  surfaced by retrieval.

## Scoping

- `--project tropical` returns only `tropical` hits (a second-project doc is excluded);
  `--project <other>` returns only that project's; `--source <id>` restricts to one source.

## Guardrails honored

- **No Microsoft 365 writeback / no Graph calls / no embeddings** — SQLite + deterministic scoring.
- **Bounded redacted excerpts only**; full document text never returned (V19 CHECK enforced).
- **No tokens / signed URLs / `@microsoft.graph.downloadUrl` / raw delta links** in output; `web_url`
  is the plain item link used for traceability.
- **Sensitive-file routing not bypassed** — review-required / review-queued items excluded.
- **Permission tightening deferred** — no delegated scope or broad Graph file consent changed; the
  broad `Files.ReadWrite.All` consent remains a documented, deferred risk (see
  `22-deferred-permission-tightening-record.md`).

## Tests

`tests/test_graph_files_retrieval.py` (6 tests): source-linked ranked hit (drive_item / web_url /
project / parser_output_id == extraction_id / processing_receipt_id); bounded + redacted excerpt
(≤2000, redaction markers preserved, no full-text/delta-link leak); project & source scoping;
review-routed exclusion (review_required run + open review-queue item absent); no-match returns empty;
CLI offline smoke. Regression: `test_graph_files_controlled_extraction.py`,
`test_graph_files_review_routing.py`, `test_repo_sensitive_scan.py`, `test_mutation_lockout.py` green.
`construction-agent validate` 4/4 (schema_version=19). The Prompt 17 matrix command
`graph files retrieve --project tropical --query "RFI submittal meeting minutes" --json` returns
`ok: true` with one source-linked hit.
