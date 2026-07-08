# N8C-23 — Structured Intelligence Artifact Workspace

## Purpose

N8C-23 lets a connected LLM client (ChatGPT / Grok / Claude Desktop) act as the second-brain
**drafting and review UI** while the NAS MCP server remains the **records authority**. When the
operator says "document this session," the client stages a bounded session capture and a set of
artifact proposals; the operator reviews them; and only after an explicit, server-recorded approval
does the server validate, write canonical structured records, and materialize Obsidian cards.

Nothing the client does is canonical. Staging and review touch only workspace tables. The single
place a canonical record or a vault card comes into existence is behind a server-minted approval,
a bound validation receipt, and a server-derived idempotency key.

## Schema (V112, additive)

Two DDL modules add 15 tables (migrator `LATEST_SCHEMA_VERSION = 112`):

**Artifact workspace** (`store/pa_artifact_workspace_tables.py`):
`pa_session_captures`, `pa_artifact_proposal_bundles`, `pa_artifact_proposals`,
`pa_artifact_proposal_versions`, `pa_artifact_review_decisions`, `pa_artifact_promotion_bundles`,
`pa_artifact_validation_receipts`, `pa_canonical_artifacts`, `pa_artifact_links`,
`pa_promotion_receipts`, `pa_artifact_repair_tasks`.

**Client tool manifest** (`store/pa_client_tool_manifest_tables.py`):
`pa_client_tool_manifests`, `pa_tool_manifest_entries`, `pa_workflow_route_recipes`,
`pa_tool_manifest_refresh_proposals`.

All tables follow the existing additive convention (TEXT PKs, `_json` TEXT columns,
`created_at/updated_at DEFAULT CURRENT_TIMESTAMP`, `CHECK(x IN (...))` enum guards, separate
`CREATE INDEX IF NOT EXISTS`). Migration is idempotent (`CREATE ... IF NOT EXISTS` + version guard).

## Lifecycle

```
session capture  →  proposal bundle  →  review decisions  →  validation  →  promotion  →  materialization
   (staged)          (staged, versioned)   (server-minted     (receipt +    (canonical DB    (Obsidian cards +
                                            approval id)        hash bind)    rows)            receipt + manifest)
```

Proposals move through `pending → approved | rejected | needs_revision | session_note_only | deferred`.
Revisions never overwrite v1 — each `pa_artifact_proposal_revise` appends a `pa_artifact_proposal_versions`
row. Bundles move `open → validated → promoted | partial_failure`.

## Tool surface (23 `pa_*` tools)

- **Read / advisory:** `pa_session_capture_get`, `pa_artifact_proposal_list/get/compare`,
  `pa_artifact_proposal_plan_promotion`, `pa_artifact_promotion_validate`,
  `pa_artifact_promotion_receipt_get`, `pa_artifact_manifest_get`, `pa_vault_path_resolve`,
  `pa_canonical_artifact_list/get`, `pa_tool_manifest_get/tool_help/workflow_get/freshness_check/review_plan`.
- **Staged write (workspace tables only):** `pa_session_capture_stage`,
  `pa_artifact_proposal_stage/revise/review`, `pa_tool_manifest_refresh_stage`.
- **Canonical write (approval + validation + idempotency):** `pa_artifact_promotion_apply`,
  `pa_tool_manifest_refresh_promote`.

None of these tool names contain the write-verb substrings (`write/upsert/delete/create/persist`)
guarded by `test_ai_outputs_is_the_only_write_tool`; none is added to `ALL_ASSISTANT_TOOLS`; none is
reachable through the N8C-22 assistant gateway (`hb_assistant_tool_query`). They are exposed only
through their own explicit registrations and gates (`HB_MCP_ARTIFACT_WORKSPACE`,
`HB_MCP_CLIENT_TOOL_MANIFEST`, both default-on kill-switches).

## Safety invariants

- Staging and review never write the vault.
- Promotion requires a server-minted `operator_approval_id` **plus** a prior validation pass **plus**
  a server-derived idempotency key. See [canonical-artifact-promotion-workflow](canonical-artifact-promotion-workflow.md).
- Card writes are DB-first, then temp-file + atomic-rename; a failed card leaves the canonical row in
  `promotion_partial_failure` with a `pa_artifact_repair_tasks` entry (never a half-written card).
- Duplicate detection blocks silently re-promoting an existing decision / preference / open-loop.
- Every proposal and card body passes `redact_text`.
- The path resolver refuses traversal, absolute, outside-root, hidden/protected, and **any new
  top-level vault folder** — cards land only in existing folders.
- `ai_outputs_card_upsert` remains the only pre-existing sanctioned write and stays unreachable via
  the gateway. N8C-23 adds narrowly-scoped, approval-gated writes; it does not add any broad, raw, or
  arbitrary write surface.

## Relationship to N8C-22

N8C-22 exposed the 78 canonical assistant tools to connected clients plus a fallback gateway. N8C-23
is strictly additive: the 78-tool count, the finality guards, and the write-heuristic guard all stay
green, and the gateway allowlist is unchanged.
