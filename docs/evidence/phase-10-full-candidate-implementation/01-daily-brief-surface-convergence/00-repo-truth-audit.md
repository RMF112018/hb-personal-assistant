# Repo-Truth Audit — Daily Brief Surface Convergence (Prompt 01)

Audited the live code paths the prompt names before implementing. Findings:

## Existing surfaces (all present)

| Concern | Location | State before this candidate |
|---|---|---|
| Daily-run orchestrator | `src/hb_assistant/construction/second_brain/local_ai/daily_run.py` `run_daily_local_agent()` | Renders browser HTML + Obsidian note + redacted status from the pipeline brief. |
| Browser HTML render | `…/local_ai/daily_run_html.py` `render_daily_run_html()` | Renders synthesis cards + deterministic section cards; egress-scrubbed + fail-closed. |
| Obsidian markdown | `…/daily_brief/output.py` `write_brief_output()` (marker-bounded, atomic) | Writes the `markdown` content the orchestrator passes. |
| Redacted status file | `daily_run.py` `_write_status()` | Counts/paths/timestamps only; `~/…` redacted paths. |
| V45 pending section builder | `…/daily_brief/email_followup_pending.py` `build_pending_email_enrichment_section()` + `render_pending_enrichment_markdown()` | Raw-free, source-linked, clean-degrading. Labels: `Model-enriched / pending review`, `low confidence / needs review`. |
| V45 table | `store/migrator.py` `email_followup_enrichments` (V45) + `_P10_GUARDS` (13 CHECK(=0) columns) | Structured/redacted fields + hashes + source refs only. |
| `--with-email-raw-enrichment` flag | `cli/second_brain.py` `second_brain_daily_run_run()` | Attached the section to the **JSON payload only** (`_attach_email_raw_enrichment_section`). |
| `--with-intelligence` flag | same | Attaches advisory model intelligence to the JSON payload only. |

## The convergence gap

`build_pending_email_enrichment_section` was wired **only** into the standalone JSON-payload helper
(`second_brain.py:9797`). It did **not** reach the operator-facing render surfaces: the browser HTML
(`render_daily_run_html`) and the Obsidian note (`markdown`) never contained the pending section, and
the status file carried no pending summary. So `--with-email-raw-enrichment`'s help (“surface … in
the brief”) overstated reality — it enriched the payload, not the surfaces.

## Decision (surgical convergence)

1. Build the pending section once in `run_daily_local_agent` (clean-degrading, guarded).
2. Append `render_pending_enrichment_markdown(section)` to the Obsidian `markdown`.
3. Pass `pending_followup=section` to `render_daily_run_html`; add a dedicated raw-free card,
   emitted **before** the brief body so it survives the degraded-synthesis path and never requires
   model synthesis.
4. Add a redacted `pending_followup` summary (counts/labels only) to the status file + run payload.
5. Reword `--with-email-raw-enrichment` help to match reality: the rendered brief now always surfaces
   pending review-safe rows; the flag only adds the same data to `--json`.

No schema change (V45 already exists). No external writeback. No raw content on any surface.
