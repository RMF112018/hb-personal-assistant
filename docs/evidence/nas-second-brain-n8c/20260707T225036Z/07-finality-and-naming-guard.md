# N8C-20 — finality + naming guard

## Live inventory proof (fresh DB, all tools registered)

```
TOTAL_TOOLS 121   ASSISTANT_TOOLS 78   QUALITY_TOOLS 6
QUALITY_TOOL_NAMES ['assistant_get_quality', 'assistant_get_quality_export',
                    'assistant_get_quality_findings', 'assistant_get_quality_summary',
                    'assistant_get_quality_targets', 'assistant_list_quality']
FINALITY_VIOLATIONS []
ai_outputs_card_upsert present: True
```

## Finality guard

Every assistant tool name is scanned for the forbidden substrings: execute, dispatch, schedule, remind, send,
build, apply, write, create, delete, persist, upsert, accept, reject, defer, dispose, generate, extract, scan,
reindex, rebuild — plus the N8C-20 additions **repair** and **evaluate**. The six quality tool names use only
`list` / `get` / `findings` / `targets` / `summary` / `export` verbs and clear every substring. Zero
violations across all 78 assistant tools (`test_no_write_build_or_evaluate_tool_registered`).

## Naming discipline

- The MCP tool group is named `quality` (not `evaluate`) precisely so the finality guard's `evaluate`
  substring stays clean — `evaluated` is only ever a DB run-record status, never a tool/route/command name.
- `assistant_get_quality_export` uses `export` (a read verb), not `dump`/`write`.

## Only sanctioned remote write preserved

`ai_outputs_card_upsert` remains the single registered write tool. Under `HB_MCP_SAFE_MODE=1`, quality reads
still succeed while `ai_outputs_card_upsert` is denied with `safe_mode_active`
(`test_reads_are_not_writes_safe_mode`). `DENIED_TOOL_NAMES` (raw_sql/sql/shell/exec/read_file_absolute/
hb_output_delete) is unchanged.
