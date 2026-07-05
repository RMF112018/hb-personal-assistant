# N8C — Memory Classes & Mutation Boundaries

> Status: **contract / normative**. Written in N8C-1. Defines the four memory classes and the
> read/write boundaries every N8C process must honour. Companion:
> [`n8c-personal-intelligence-operating-layer.md`](./n8c-personal-intelligence-operating-layer.md).

## 1. Four memory classes

- **Immutable raw** — original files, raw `.eml`, source documents, raw imported DB rows
  (Procore/email/calendar/schedule/financial). **Never mutated** by any N8C/vault/intelligence
  process.
- **Readable archive** — parsed `.eml` vault notes, full source-preserving archive notes, other
  human-readable records that preserve original content.
- **Compiled** — source cards, entity/concept/domain/project pages, synthesis notes, decision pages,
  context packs. Machine-generated, citation-backed, safe to regenerate.
- **System records** — index rows, graph edges, enrichment jobs, receipts, staleness markers, claim
  records, memory-health records.

## 2. DB mutation boundary

DB tables are **raw unless explicitly owned** by indexing/enrichment/graph processes. N8C processes
may **read** raw DB records broadly through approved surfaces, but may only **mutate** explicitly
owned `assistant_*` / index / enrichment / graph / receipt tables. Raw and imported domain tables
(Procore/email/calendar/schedule/financial) are never written by vault/intelligence processes.

As of N8C-1 this boundary is trivially satisfied: no schema change is made
(`LATEST_SCHEMA_VERSION = 99`) and no DB row is written by this slice.

## 3. Vault write boundary

- **User-authored Obsidian notes are raw/user-authored by default.** They may be *processed* for
  summaries, links, lint, and relationship suggestions, but are **not freely rewritten**. Only a
  backend-applied, policy-gated managed block/page patch may touch them.
- **Compiled pages** (cards, entity/concept/domain pages) are owned by the assistant and may be
  regenerated; they must cite source cards/claims and carry neutral managed metadata.
- The only sanctioned **remote** vault write remains `ai_outputs_card_upsert` — folder-locked to
  `AI Outputs/`, SHA-gated, backup-before-overwrite, receipted. N8C-1 does not add any other write.

## 4. `.eml` raw / archive / card model (all three preserved)

1. **Raw `.eml`** — immutable original.
2. **DB records** — where available (imported), raw/immutable.
3. **Readable Email Archive vault note** — full-fidelity Markdown (body + reply chain + headers +
   attachment metadata); raw Message-ID/addresses/participant lists live **only** here
   (`obsidian_mcp/source_email_archive.py`).
4. **Separate source/summary card** — graph-safe facts only (hashed message-id, sender/recipient
   **domains**, participant **count**) so connected agents navigate email **without reading raw
   bodies by default**. Attachment cards inherit identity and link back to the parent.

Email is a **link-only** `source_kind` (no `_text`/`_chunks`), so raw email bodies are never fed to a
model.

## 5. Ownership recap

NAS/backend owns identity, canonical writes, guardrails, the Qwen queue, receipts, and rollback.
MacBook/Qwen owns local model execution and *proposals* only; it never mutates raw sources, canonical
pages, or raw DB tables as normal workflow. Manual MacBook DB access is triage/research only and is
never a feature dependency.
