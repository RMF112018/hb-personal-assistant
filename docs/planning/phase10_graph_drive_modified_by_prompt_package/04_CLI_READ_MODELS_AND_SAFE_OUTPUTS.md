# 04 — CLI, Read Models, and Safe Outputs

## Objective

Expose enough verification/read-model support to prove the required metadata is captured without leaking raw file/user metadata into committed evidence.

This prompt may be code-only, docs-only, or no-op if existing surfaces are sufficient. Decide based on repo truth.

## Requirements

The system should let an operator confirm, safely, that the DB contains:

- project reference coverage;
- folder/path coverage;
- file name coverage;
- modified date/time coverage;
- modified-by display name coverage.

But default command/evidence output must not dump raw values.

## Acceptable safe outputs

Safe CLI/read-model output may include:

- row counts;
- non-null counts;
- percentage coverage;
- column names;
- source location IDs;
- project keys if those are already safe in repo convention;
- redacted sample values;
- hashes or truncated opaque IDs;
- booleans.

Avoid printing:

- raw file names;
- full folder paths;
- web URLs;
- raw modified-by display names;
- emails/UPNs;
- tenant/user IDs unless hashed or already treated as safe.

## Possible CLI additions

If useful and consistent with repo conventions, add a command such as:

```bash
hb-assistant graph files coverage --json
```

or extend an existing files/drive status command.

Output example:

```json
{
  "ok": true,
  "table": "construction_drive_items",
  "row_count": 1234,
  "coverage": {
    "project_reference": 1200,
    "folder_path": 1234,
    "file_name": 1234,
    "last_modified_datetime": 1234,
    "last_modified_by_display_name": 900
  },
  "raw_values_emitted": false
}
```

## Tests required

1. coverage command returns JSON;
2. command does not print raw sample values by default;
3. counts are correct on fixture DB;
4. missing modified-by columns fail clearly if migration not run;
5. read model includes modified-by fields only where explicitly intended.

## Commit behavior

If CLI/read-model code changes are made, commit them.

Suggested commit message:

```text
feat(graph-files): add safe drive metadata coverage reporting
```

If no code changes are necessary, produce a no-code audit note and proceed.
