# 172 — Phase 09 Addendum: Claude Scheduled-Task Render Templates

**Status:** New operator-facing prompt templates + static validation proof for Claude daily-brief rendering.
**Schema:** unchanged (V39; no migration; no runtime retrieval/MCP behavior change). **Version:** 1.2.0-phase-09-addendum (package: Daily Brief / MCP Handoff & Rendering, Prompt 03).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-daily-brief-mcp-handoff/claude-daily-brief-scheduled-task-template.md`, `claude-daily-brief-manual-run-template.md`, `claude-rendering-template-proof.{json,md}`.
**Builds on:** record 170 (daily-brief packet), record 171 (`hb_daily_brief_packet` MCP tool).

---

## 1. Objective

Give the operator ready-to-use Claude prompts (a scheduled task and a manual one-off) that render the
approved daily-brief packet into a concise human-readable executive brief — calling only the MCP packet
tool, preserving every warning, making no determinations, and treating the rendered output as
narrative/advisory.

## 2. Templates

Canonical templates live in the established template home `resources/templates/`:
`claude_daily_brief_scheduled_task.md` (normal scheduled task) and `claude_daily_brief_manual_run.md`
(manual testing variant). Both reference the real MCP tool `hb_daily_brief_packet` (noting it maps to
the suggested `construction_daily_brief_packet` / `get_daily_brief_handoff`) and instruct Claude to:
call only that tool; use only the returned packet; request no raw records; call no direct
database/Graph/Procore/vector/calendar/email/memory-mutation/filesystem tools; make no
legal/financial/safety/claim/payment/entitlement/schedule-certification/contractual determinations;
preserve review-required + stale/low-confidence + advisory-only warnings; include source coverage and
suggested follow-up questions; stay concise/executive. Output format is the 7 sections + `## Advisory
Notice`. Each ends with the storage policy: rendered output is **not source truth** and must only go to
a rendered/narrative/advisory location, never imported into accepted memory / vector index / source
manifest / source-linked proof / Procore/Graph/source systems.

These are **scheduled-task prompts** (operator-pasted), not MCP server prompts; the MCP prompts registry
(locked at 5) is intentionally untouched.

## 3. Proof & CLI

`mcp/render_template_proof.py` → `build_claude_render_template_proof` loads both templates from
`resources/templates/`, asserts 29 required substrings/sections per template (tool reference, use-only,
no-raw, forbidden direct tools, no-determination, warning preservation, source coverage, follow-up
questions, the 7 section headers, Advisory Notice, storage-policy markers), scans templates + proof for
raw-shaped values (`_assert_no_raw`, fail-closed), and writes the proof JSON+MD plus faithful evidence
copies of both templates. Fail-closed `ClaudeRenderTemplateError` if a template is missing. CLI:
`hb-assistant second-brain mcp daily-brief-render-template-proof --json`.

## 4. Validation

`ruff`/`mypy` clean. `tests/test_phase_09_claude_render_template.py` (9 tests) green: proof passes, all
required clauses/sections present, forbidden-tool + no-determination language present, warning +
storage-policy preservation, no-raw clean, evidence written, fail-closed on a missing template. The MCP
CLI/handoff suites stay green. The pre-existing `test_phase_08d_schema_v37` lifecycle-classification
failure is unrelated (fails identically on clean `HEAD`).
