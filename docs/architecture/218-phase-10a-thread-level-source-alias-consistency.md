# 218. Phase 10A — Thread-level source-alias consistency for multi-message packets

Date: 2026-06-08

Package: HB Construction Intelligence — Phase 10 / 10A Local Action Intelligence (repo-truth update)

## Context

Follow-up to ADR 217 (source-ref aliases). A live dry-run over 10 email threads produced candidates,
but 7/10 were rejected `source_alias_not_in_packet` for aliases (`src_2..src_6`) the model saw in the
prompt, while diagnostics showed `source_alias_count=1`. Root cause: `_build_prompt` displayed an
index-based fallback alias `f"src_{i}"` for each excerpt. When a thread's packet messages have no
`id`/`message_id_hash`, `build_email_thread_action_packet` writes message `id=None` and its
`content.threads[0]` has no `thread_ref` key, so `_build_raw_excerpts` yields excerpts with
`source_ref=None` (excluded from `ordered_refs`). Only the thread ref is registered (`src_1`), yet the
prompt rendered `src_1..src_N` by excerpt index — unregistered aliases the model dutifully cited and the
extractor (correctly) rejected.

## Decision

`_build_prompt` now displays **only registered aliases**, with a **thread-level preference**:
- `thread_alias` = the registered alias whose family is `email_thread_raw_context` (always `src_1` for
  thread/related packets, since `packet["source_refs"][0]` is the thread ref); `default_alias` = the
  first registered alias.
- Per excerpt: email-family excerpts (`email_message_raw_content`/`email_thread_raw_context`) display
  `thread_alias` (so all messages of one thread cite the same `src_1`); otherwise the excerpt's own
  registered alias; otherwise `thread_alias`/`default_alias`. If no registered alias exists, the
  `source_alias:` line is omitted — the `f"src_{i}"` fallback is removed entirely.

This guarantees every displayed `source_alias` ∈ `allowed_source_aliases`. Alias building and
resolution are unchanged: `src_1` resolves to the canonical thread ref with `email_thread_raw_context`;
registered per-message/event aliases still resolve; truly invented aliases (`src_999`, `<excerpt1>`)
still reject `source_alias_not_in_packet`.

## Verified (mock)

- Multi-message thread (messages without ids): prompt shows `src_1` for all 6 message excerpts; every
  displayed alias ∈ `allowed_source_aliases`; no `src_2..` leak.
- Model citing the displayed `src_1` → accepted, persists with `source_family=email_thread_raw_context`,
  canonical thread ref.
- `src_999` / `<excerpt1>` → still rejected `source_alias_not_in_packet`.

## Guardrails / non-goals

Dry-run default; no live `--apply`; no email/calendar/Procore/MCP-raw/cloud-LLM writeback; diagnostics
redacted. No schema/migration/contract change; `_build_prompt` display logic only; no README/ledger
bump. No apply-path live persistence recommended until a live dry-run returns accepted candidates or
explicit schema/business/unresolved-alias rejections.
