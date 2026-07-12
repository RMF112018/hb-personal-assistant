# A2 — manifest semantic diff + regeneration evidence

Purpose: record the EXACT semantic change to the tool surface and prove it is limited to intended semantics —
the client-visible `assistant_source_file_read` contract now states its real behavior, the checksum
regenerates deterministically, direct/gateway parity holds, and no unrelated tool metadata drifted.

## History (two corrective passes)
- **A2 corrective #1** corrected only the `assistant_get_source` *docstring*. That did NOT move the semantic
  checksum, because the checksum derives from each tool's canonical manifest **`purpose`**, not the docstring
  body — `assistant_get_source`'s purpose was already the accurate navigation-family text.
- **A2 corrective #2 (this pass)** corrects the actual defect the reviewer flagged: the client-visible
  canonical **`purpose`** of `assistant_source_file_read` still read the generic family fallback
  `"Indexed NAS source-file discovery."`, which discloses none of the read tool's real contract. This pass
  adds a proper `tool_entry_manifest` entry, so the purpose changes — and the checksum changes **by design**.

## The semantic change (exactly one tool purpose)
`src/hb_assistant/obsidian_mcp/tool_entry_manifest.py` — new `assistant_source_file_read` entry:

| Field | Before | After |
|---|---|---|
| `purpose` | `Indexed NAS source-file discovery.` (generic family fallback) | `Read a bounded excerpt from one trusted indexed NAS source file; not complete-file retrieval. Requires a safe root and an exact selected file; the excerpt may be truncated or fall back to the indexed excerpt.` |
| `use_when` | (none — family fallback) | `You selected an exact source_id/path from search on a safe root and need a short verbatim excerpt to confirm content.` |
| `do_not_use_when` | (none) | `The root is not trusted, you need the whole file, or you only need file details (use assistant_source_file_metadata) or discovery (use assistant_source_file_search).` |
| `examples` | (none) | `["Read the top of the matched contract PDF", "Show the first lines of the selected file"]` |
| `common_failure_modes` | (none) | untrusted/unready root (blocked_root_unready); unsupported binary type; excerpt truncated at the bounded limit; indexed-excerpt fallback when a live read is unavailable |

The corrected purpose discloses all four required facts: **bounded excerpt**, **no complete-file retrieval**,
**root-trust enforcement (safe root required)**, and **truncation / indexed fallback**.

## Regenerated `semantic_surface_checksum` — before → after (change is expected)
Probe: `manifest_probe.py` builds the live tool index and calls the official `build_manifest(...)` with a
pinned runtime commit and pinned `now`, so only the semantic surface perturbs the checksum.

| Tree | `semantic_surface_checksum` |
|---|---|
| pristine `origin/main` `9c27839b` | `sha256:3eb81b4d765e6ab812663fd22784b8ed37054f53d9f1e1bcc5d83bb5c4bf09fc` |
| A2 corrective #1 (`get_source` docstring only) | `sha256:3eb81b4d765e6ab812663fd22784b8ed37054f53d9f1e1bcc5d83bb5c4bf09fc` (unchanged) |
| **A2 corrective #2 (`read` purpose corrected)** | `sha256:16af53d339a5850a8d88e7c477be84bca67834119843ecdda21eae6917a53b72` |

The change from `…c4bf09fc` → `…a53b72` is the intended, inspected result of the corrected `read` purpose —
**not** a forced/hand-edited checksum. Probe outputs: `manifest-checksum-originmain.txt` (old) and
`manifest-checksum-a2corrective2.txt` (new).

## No unrelated tool-metadata drift — per-source-tool `purpose` after
| Tool | `purpose` on A2 corrective #2 | Changed vs origin/main? |
|---|---|---|
| `assistant_get_source` | `Read-only source/card/note navigation.` | no |
| `assistant_source_file_metadata` | `Inspect metadata for one indexed source file before a bounded read.` | no |
| `assistant_source_file_read` | `Read a bounded excerpt … may be truncated or fall back to the indexed excerpt.` | **YES (intended)** |
| `assistant_source_file_search` | `Search indexed NAS source file contents and filenames; not for Obsidian vault notes.` | no |
| `assistant_source_files_list` | `Indexed NAS source-file discovery.` | no (genuinely discovery) |

Exactly one purpose changed — `assistant_source_file_read`. No other tool's purpose drifted.

## Direct / gateway parity + freshness + official regeneration
- The freshness-guard and parity guards that rebuild the live surface pass:
  `test_tool_manifest_freshness_guard.py`, `test_manifest_schema_parity.py`,
  `test_n8c_client_exposure_bridge.py` are GREEN (see `a2-validation-client-surface.txt`), and the A2 suite's
  `test_direct_and_gateway_trust_agree` confirms one authority behind both routes. The freshness guard compares
  the live-rebuilt checksum to the stored one dynamically — there is **no hard-coded checksum baseline** to
  hand-edit.
- The frozen manifest is a SQLite row rebuilt from the live surface at registration
  (`bootstrap_persisted_manifest` / `seed_frozen_schema_index`); re-freezing is the official generation path,
  so the new `…a53b72` checksum is produced by regeneration, not by editing a stored value.

## Docstring note
The `assistant_source_file_read` runtime docstring (`tool_registration.py`) was already accurate ("Bounded,
extension-gated read … Never returns a full raw file or an absolute path"), so it needed no change; the defect
was solely the missing canonical entry purpose, now added. `assistant_get_source` is a **separate** navigation
tool (family purpose `Read-only source/card/note navigation.`) — its corrective did not and cannot substitute
for correcting `assistant_source_file_read`.
