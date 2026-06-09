# Graph Drive Modified-By Metadata Evidence

Date: 2026-06-09
Branch: `experiment/graph-drive-raw-metadata-modified-by`

## Scope

This evidence covers Phase 10 SharePoint/OneDrive Graph drive-item operational metadata capture for:

- source reference and project reference coverage;
- folder path and explicit folder-name coverage;
- file-name and modified timestamp coverage;
- Graph `lastModifiedBy` identity coverage in local SQLite operational metadata.

No raw file names, folder paths, URLs, user names, emails, user IDs, or raw identity JSON are recorded here.

## Schema

Schema head: `44`

Table changed: `construction_drive_items`

Columns added:

- `parent_folder_name`
- `last_modified_by_display_name`
- `last_modified_by_user_id`
- `last_modified_by_email`
- `last_modified_by_application_display_name`
- `last_modified_by_raw_json`

## Validation Commands

Targeted tests:

```bash
/Users/bobbyfetting/hb-personal-assistant/.venv/bin/pytest tests/test_graph_files*.py -q
```

Static checks:

```bash
/Users/bobbyfetting/hb-personal-assistant/.venv/bin/ruff check src/hb_assistant/cli/graph.py src/hb_assistant/construction/drive_item_bridge.py src/hb_assistant/construction/graph/baseline_crawler.py src/hb_assistant/construction/graph/delta_sync.py src/hb_assistant/construction/graph/drive_item_indexer.py src/hb_assistant/construction/store/repositories.py src/hb_assistant/store/migrator.py tests/test_graph_files_drive_item_indexing.py tests/test_graph_files_endpoint_contract.py
/Users/bobbyfetting/hb-personal-assistant/.venv/bin/ruff format --check src/hb_assistant/cli/graph.py src/hb_assistant/construction/drive_item_bridge.py src/hb_assistant/construction/graph/baseline_crawler.py src/hb_assistant/construction/graph/delta_sync.py src/hb_assistant/construction/graph/drive_item_indexer.py src/hb_assistant/construction/store/repositories.py src/hb_assistant/store/migrator.py tests/test_graph_files_drive_item_indexing.py tests/test_graph_files_endpoint_contract.py
/Users/bobbyfetting/hb-personal-assistant/.venv/bin/mypy src/hb_assistant/cli/graph.py src/hb_assistant/construction/drive_item_bridge.py src/hb_assistant/construction/graph/baseline_crawler.py src/hb_assistant/construction/graph/delta_sync.py src/hb_assistant/construction/graph/drive_item_indexer.py src/hb_assistant/construction/store/repositories.py src/hb_assistant/store/migrator.py
```

DB-copy proof:

```bash
cp '<operator-db>' /tmp/hb_graph_drive_modified_by_proof.sqlite
/Users/bobbyfetting/hb-personal-assistant/.venv/bin/pytest /tmp/test_hb_graph_drive_modified_by_migrate.py -q
/Users/bobbyfetting/hb-personal-assistant/.venv/bin/pytest /tmp/test_hb_graph_drive_modified_by_fixture_backfill.py -q
/Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant graph files index --source sp_2023projects_23_435_01_tropical_sl --max-pages 1 --apply --db /tmp/hb_graph_drive_modified_by_proof.sqlite --json
/Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant graph files coverage --db /tmp/hb_graph_drive_modified_by_proof.sqlite --json
```

No-writeback proof:

```bash
/Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant graph files no-writeback-proof --json
```

## Results

- `tests/test_graph_files*.py`: passed.
- `ruff check`: passed.
- `ruff format --check`: passed.
- `mypy`: passed on changed source modules.
- DB copy migration proof: passed.
- Fixture-backed DB-copy idempotency proof: passed.
- Bounded live Graph metadata apply to DB copy: completed twice against the copy only.
- Graph files no-writeback proof: passed.

Final count-only DB-copy coverage after bounded apply:

```text
row_count|1000
source_reference|1000
project_reference|202
folder_path|998
folder_name|201
file_name|1000
last_modified_datetime|1000
last_modified_by_display_name|202
last_modified_by_user_id|136
last_modified_by_email|136
last_modified_by_application_display_name|1
last_modified_by_raw_json|202
raw_values_emitted|false
missing_columns|0
```

## Backfill

Existing production rows remain valid with NULL values until reindexed. Backfill is the existing Graph files indexer pointed at the intended operational DB, but production DB mutation requires explicit approval before running apply mode.

Recommended production command after approval:

```bash
hb-assistant graph files index --source <source_id> --max-pages <bounded_pages> --apply --json
```

## Limitations

- Coverage depends on Graph returning `lastModifiedBy`; the bounded live proof showed nonzero coverage for the tested source.
- `parent_folder_name` is deterministically derived from `parentReference.path`; root-level parent paths can have no folder-name component and remain NULL.
- The local DB stores raw identity JSON by design; committed outputs must remain count-only or redacted.
