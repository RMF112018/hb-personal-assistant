# N8C-21 — finality & write-boundary proof

- **Finality guard:** no assistant tool name (all 78) contains any of the 23 base forbidden substrings plus
  the N8C-20 additions `repair` / `evaluate`. Zero offenders
  (`test_finality_guard_across_every_assistant_tool`).
- **Denied raw tools:** `DENIED_TOOL_NAMES` = {raw_sql, sql, shell, exec, read_file_absolute, hb_output_delete}
  — each is denied on dispatch (`test_denied_tool_names_blocked`).
- **Only sanctioned write:** `ai_outputs_card_upsert` is the only tool that actually mutates state. Every other
  registered tool whose NAME contains a write verb is a read-only `*_plan` generator (its build/apply path is
  CLI-only and never exposed remotely). No ASSISTANT tool is write-ish at all
  (`test_ai_outputs_is_the_only_write_tool`).
- **Read-only data plane:** every assistant tool is served from a read-only DB snapshot
  (`mode=ro&immutable=1` + `PRAGMA query_only=ON`); there is no live-DB fallback and no remote write path other
  than `ai_outputs_card_upsert`.
