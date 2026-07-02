# Direct-File / Manifest Source Selection — Findings (count-only)

## Result: **exact-file selection works when directory enumeration fails**

The Tropical SynologyDrive project root and the target subroot both fail `os.scandir` with EINTR
(dormant / on-demand), so neither bounded subroot traversal nor a root walk can enumerate the file. A
**direct `lstat` of the exact file** (`<bounded_pdf_file>`, relative to `--source-root`) succeeds and
classifies **readable** (genuinely local: `st_blocks>0`, not dataless). The new `--include-file` /
`--source-manifest` selectors resolve that file **without any parent directory listing**, so it is now
processable. Identity is still derived from `--source-root` (project `23-435-01` / `tropical`).

## Evidence (read-only; stat/lstat only; no byte reads; no hydration; no writes)

### Direct-file probe (`01-direct-file-probe/probe-include-file-safe.json`)
- `source_root_exists: true`, `source_root_listable: false`, `interrupted_system_call_count: 1`
  (root scandir EINTR — the folder will not enumerate).
- `include_files_requested_raw: 1`, `include_files_validated: 1`, `include_files_lstat_ok: 1`,
  `include_files_selected_readable: 1`.
- `include_files_missing: 0`, `include_files_not_files: 0`,
  `include_files_unavailable_or_placeholder: 0`, `include_files_unsupported_ext: 0`,
  `include_files_containment_rejected: 0`.
- `files_seen: 0`, `read_probe_mode: stat_only` — nothing under the root was enumerated, nothing opened.

### Project-corpus dry-run (`02-project-corpus-dryrun/corpus-index-dry-run-summary-safe.json`)
- `mode: dry-run`; identity `project_number 23-435-01` / `project_key tropical` /
  `procore_project_id 2525840` (basis: folder + procore number + key).
- `include_files_requested_raw: 1`, `include_files_validated: 1`, `include_files_selected: 1`;
  `files_selected: 1`; `by_extension {".pdf": 1}`; `by_folder_bucket` keys redacted to
  `<bounded_bucket_1>` (real names only in `local-sensitive/`).
- All write/queue/Ollama counters **0**: `cards_generated 0`, `files_indexed_new 0`, `queue_delta 0`,
  `ollama_calls 0`, `metadata_only 0`. `generated_before {"not_generated": 195}` (dry-run returns
  before any DB/vault mutation).

### Email-archive negative control (`03-email-archive-dryrun/eml-archive-dry-run-summary-safe.json`)
- Same PDF `--include-file`: `include_files_validated: 1`, **`include_files_unsupported_for_eml: 1`**,
  `include_files_selected: 0`, `eml_selected: 0`, `eml_found: 0`.
- No writes: `archive_notes_created 0`, `source_cards_generated 0`, `graph_facts_written 0`,
  `queue_delta 0`, `ollama_calls 0`, `generated_note_delta 0`, `vault_markdown_delta 0`. Empty
  `by_folder_bucket` (nothing selected → no folder name emitted).

## Tests (`04-tests/pytest-summary-safe.txt`)
75 passed across selection helpers, subroot safety, probe, project-corpus, eml-archive, archive
routing, vault↔DB reconcile, and generated-artifact reset. Includes the crux test: an exact file is
selected while **every `os.scandir` raises EINTR** (selection depends on `lstat` alone), plus
absolute/`..`/escape refusals, missing/dir/unsupported counting, the EML `unsupported_for_eml` negative
control, and manifest file/subroot mixing with a rejected escaping entry.

## Safety posture
`lstat`-only for exact files; no `scandir`/`rglob`/`resolve`/`realpath` on cloud paths (the by-path
relative computation is lexical); placeholders never opened; dry-run only; no vault write, no DB apply,
no queue mutation, no runtime-JSON mutation, no source hydration. Safe evidence is count-only with the
source relative path / PDF filename / folder-bucket names redacted to placeholders; raw path, manifest
entries, and resolved detail live only under `local-sensitive/` (gitignored).

## Code changed = yes
`src/hb_assistant/obsidian_mcp/source_subroot.py` (+ `validate_include_file`, `classify_include_file`,
`load_source_manifest`, `classify_manifest_entry`, shared `validate_relative_under_root`) and
`--include-file` / `--source-manifest` on the two indexers + the availability probe.

## Recommended next operator step (bounded, explicit)
To ingest this file under a future authorized apply, pass the same `--include-file` (or a
`--source-manifest`) to `obsidian_source_index_project_corpus.py --apply` with the exact confirm flags
and a `--backup-dir` rollback bundle — no directory hydration required, because selection is by-path.
