# Phase 08A → 08B / 08C / 08D / 09 — Final Handoff

Explicit downstream routing from the completed Phase 08A local-first second-brain runtime
(Prompts 02–15; Prompt 09 Chat Session Memory deferred). Companion to
`final-validation-closeout.md`. All Phase 08A surfaces are read-only / dry-run-default,
metadata-only, no-writeback, no-raw-content (proofs pass).

## Phase 08B — Automation & Delivery

**Owns (deferred here):** launchd automation hardening (idempotent install/enable, health
checks, retries, weekend/holiday behavior, failure alerting, run-ledger integration); the
polished interactive **HTML** daily brief; macOS **notifications**.

**Consumes (ready now):**
- `DeliveryHandoffPayload` (Prompt 12) — `phase="08B"`, `eligible_for_delivery` flag,
  source-linked `sections` + `source_refs`, a data-only `notification_summary`
  (`channel="local_only"`, `emitted=false`), and `html_rendering` **render-data**
  (`format="render_data"`, `rendered=false`). Local-only; `external_delivery_performed=false`.
- `daily_brief_runs` + `daily_brief_source_refs` (V26) — persisted brief runs with
  `evaluation_run_id` + `output_path_redacted/hash`.
- `launchd_schedule_previews` (V26) + the scheduling runbook
  (`docs/runbooks/phase-08a-second-brain-daily-brief-scheduling.md`) — the dry-run plist
  preview (20:00 local → following day's brief, apply mode) to harden into a real install.

**Readiness confirmed:** the daily brief is evaluation-gated (apply blocked unless evaluation
passes), local-only, and source-linked; the launchd install is a dry-run preview only (no
plist written, no `launchctl` invoked). 08B turns these payloads/previews into rendering +
delivery + a hardened schedule.

## Phase 08C

**Available substrate:** the internal service-agent registry (A01–A09), the allowlisted
retrieval broker, the research-packet-before-synthesis + output-evaluation-before-apply
discipline, tiered review (Tier-3 never auto-accepted), and memory provenance / quality
signals. No Phase 08A blocker; 08C builds on this substrate per the package roadmap. (Scope
stated factually — not invented here.)

## Phase 08D — MCP Exposure

**MCP readiness contract (already encoded; 08D implements):**
- `phase_08a_agent_tool_contract.json` → `mcp_future_exposure_rule`:
  **"Expose workflows only; never expose stores."**
- Each agent in the registry declares `allowed_tool_groups` / `denied_tool_groups`
  (e.g. `external_writeback`, `arbitrary_sql`, `raw_filesystem` are denied) — the MCP surface
  must honor these allowlists.
- The data-quality gate `mcp_exposure` is `deferred_not_blocking` (future_phase `08D`).

**08D will:** expose the existing internal agents/workflows (retrieval, research packet,
synthesis, daily brief, memory review, review triage) over MCP, honoring the per-agent
tool-group allowlists and the no-writeback / no-raw-content guardrails; **never** expose the
SQLite stores or arbitrary SQL directly.

## Phase 09 — Embeddings (+ deferred Chat Session Memory)

- **Embeddings / semantic retrieval:** the deterministic, allowlisted retrieval broker
  (Prompt 04) + context budget is the seam — Phase 09 adds embedding-based ranking *behind*
  the broker without changing its bounded, source-linked, no-raw-content output contract.
- **Chat Session Memory (deferred Prompt 09):** the `interactive_chat_sessions` table (V26)
  and the interactive query CLI + answer synthesis agent (Prompt 08) are the seam for the
  not-yet-built Chat Session Memory agent; it should reuse the memory provenance + tiered
  review discipline (Prompt 10) and persist metadata-only.

## Cross-cutting guardrails carried into all downstream phases

External systems read-only; no source-system writeback; no raw content persisted; metadata-
only receipts with guard columns 0; dry-run defaults for write-capable local ops; Tier-3 /
high-impact never presented as final conclusions; model boundary = the Anthropic
`messages.create` call only, with metadata-only receipts. Both no-writeback proofs + the
no-raw-content proof + the data-quality gates must continue to pass in every downstream phase.
