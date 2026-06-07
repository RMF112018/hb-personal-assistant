# 21 Rollback and Stop Conditions

## Stop immediately if

- any test indicates raw restricted content was persisted;
- any external writeback occurs;
- model prompt or response is stored raw;
- Graph/Procore credentials are visible in frontend, logs, evidence, or receipts;
- `qwen3:30b` is used in scheduled/background mode without explicit config and concurrency limits;
- Obsidian writer changes text outside HB-managed markers;
- MCP exposes arbitrary SQL, raw content, or write tools;
- accepted tasks can be created without source refs.

## Rollback approach

- revert the last prompt commit;
- preserve evidence showing failure;
- add regression test before retrying;
- do not manually edit production DB except through migrations/rollback scripts reviewed separately.
