# 06 — Availability Probe Results (stat-only)

## Tool + safety confirmation
`scripts/obsidian_source_root_availability_probe.py` — confirmed read-only/stat-only from source before running:
- Stat-only by default (`--read-probe-limit` defaults to `0`); byte-reads require BOTH `--read-probe-limit>0` AND
  `--confirm-read-probe-local-files` (neither passed).
- Imports only `hb_assistant.obsidian_mcp.source_subroot` (path helpers) — **no DB, no backend, no watcher, no card
  generation**. Writes only to the output paths passed on the CLI; never to the source root.

## Where it ran (and why)
The NAS vault path is **not locally mounted**, and there is no repo checkout on the NAS, so the repo probe cannot walk
`/volume1/...` from the Mac. It was therefore run against the **local Mac vault**, which N5A proved byte-equivalent to
the NAS mirror (221 files / 155 md, sha-matched transfer). The **NAS-target** availability is proven independently by
the service-user stat proofs in `03`. This run demonstrates the read-only tooling works and corroborates the mirrored
structure.

## Result (count-only)
```
read_probe_mode      = stat_only          (0 bytes read; files_read_probe_ok=0)
source_root_exists   = true
source_root_listable = true
files_seen           = 230
files_stat_ok        = 221                 (matches mirrored file set)
candidate_doc_ext    = 155                 (markdown candidates == 155 md)
candidate_eml        = 0
unsupported_ext      = 66                  (non-md files)
temp_skipped         = 9                   (.DS_Store etc — excluded from mirror)
cloud_placeholder/unavailable = 0
permission_error     = 0
other_error          = 0
symlink_dirs_skipped = 0
```

## Interpretation
- `read_probe_mode=stat_only` + `files_read_probe_ok=0` → **no file contents were opened**; genuinely stat-only.
- `files_stat_ok=221`, `candidate_doc_ext=155` → exactly the mirrored set (221 files, 155 md), 0 placeholders,
  0 errors. Structurally consistent with the NAS mirror.
- Row/path-level detail (candidate sample paths) went to the git-ignored `local-sensitive/` dir only; committable
  output is count-only.

This satisfies the "safe stat-only availability proof runs successfully" acceptance bullet (alongside the NAS-target
svc stat proof in `03`).
