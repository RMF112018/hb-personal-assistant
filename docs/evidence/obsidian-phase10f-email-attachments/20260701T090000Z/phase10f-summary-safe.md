# Phase 10F — Email attachment source cards (count-only safe evidence)

Bounded extraction of attachments from Phase-10E-carded `.eml` files → deterministic attachment source
cards under `Source Notes/Work/` → reciprocal managed-block links between each parent email card and its
attachment cards. **Phase 10F is DETERMINISTIC-ONLY.** **No push, no PR.**

## Binaries are transient (no retained archive)

Attachments are extracted **transiently** for parsing/card generation only: each binary is written under
the guarded `Email Archive/Work/Attachments/` root just long enough to index + card the attachment, then
**always deleted** (empty per-email dirs pruned). This phase creates **no retained attachment binary
archive**. Final live state: **0** binaries remain.

## Advisory summaries: deterministic default, opt-in + quality-gated

Attachment cards carry a deterministic **pending** `hb-local-summary` block by default — the default apply
makes **no Ollama call**. A local qwen2.5:14b advisory is an **operator-only opt-in** (`--summarize`) and is
written **only if** it passes `sls.validate_advisory` (canonical four-section shape — Summary / PM
Attention / Follow-Up Questions / Limits / Uncertainty; rejects filename/size assertions, deterministic
metadata contradictions, and duplicate/noncanonical shapes); otherwise the block stays pending
(`summary_failed`).

## Correction history (this is not a pristine first-pass — it was repaired)

1. **Initial apply** (`02-apply-summary-safe.json`) carded the two attachments (binaries still persisted at
   the time).
2. **A defect was found:** a mid-session change made the qwen2.5:14b summary run **by default**, which was a
   deviation from the original *no Qwen/Ollama* guardrail and produced an unreliable summary that invented a
   filename and size. `05-apply-qwen-rerun-summary-safe.json` records that Qwen **did run** during the phase
   (`qwen_summaries_written: 2`) — retained here so the record is honest.
3. **Correction re-run** (`06-apply-correction-deterministic-safe.json`, `--apply --update`, **no
   `--summarize`**) repaired both affected cards back to **deterministic pending** summaries and reconciled
   inherited project identity. Key results: `attachment_cards_updated: 2`, `ollama_calls: 0`,
   `qwen_summaries_written: 0`, `summary_failed: 0`, `summary_model: null`, `summarize_requested: false`,
   `attachment_binaries_written: 2`, `attachment_binaries_deleted: 2`, `parent_email_cards_updated: 1`,
   `reciprocal_links_added: 2`, `queue_delta: 0`, `generated_note_delta: 0`.

## Live post-correction verification

- Both attachment cards: `hb-local-summary` block `status="pending"` (deterministic); **zero** qwen
  output remains (invented filename/size gone).
- Inherited identity is self-consistent: frontmatter `project_number: 23-435-01`, `project_key: tropical`,
  a single `project/23-435-01` tag, the visible "Related Project" line reads
  "Project (inherited from parent email): …" (no "No project number detected"), and exactly **one**
  `hb-project-identity` block — frontmatter, bullet, and block all agree.
- Exactly one `hb-email-attachment` block per attachment card; the parent card has one
  `hb-email-attachments` block listing **both** attachment cards (fully reciprocal, no one-way links).
- **0** attachment binaries remain; Attachments dirs pruned.
- **0** `obsidian_note_index` rows under `Email Archive/` — the self-index guard holds live.

## Graph (lineage-only; apply deferred to 10G)

`03-graph-proof-dryrun.json` / `04-attachment-graph-signals.json` — dry-run proof that attachment cards
contribute `same_parent_email` / `same_attachment_sha256` candidate signals. No graph apply in 10F.

## Safety

- `local-sensitive/`, `*.sqlite`, `*.log`, and the `rerun-qwen-*/` and `correction-*/` run dirs are
  git-ignored (DB backups, per-file detail rows, card backups with real filenames, third-party stderr with
  absolute paths). Committed evidence is count-only — no filenames, addresses, message identifiers, source
  paths, or Qwen output.
- Backend on `:8000` was stopped for each apply (hard-stop precondition) and restarted afterward.
