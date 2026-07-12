# A2 corrective — manifest semantic diff + regeneration evidence

Purpose: prove the A2 tool-help change is limited to intended semantics — exactly one docstring corrected,
no unrelated tool-metadata drift, the frozen `semantic_surface_checksum` regenerates identically, direct and
gateway agree, and the freeze went through the official generation path (no hand-edited checksum).

## What A2 changed on the tool surface
A2's only tool-surface edit is in `src/hb_assistant/nas_mcp/tool_registration.py`: the `assistant_get_source`
docstring's "...for full file content" overstatement was replaced with an explicit bounded-excerpt statement
noting the root-trust check. **No tool was added, removed, or renamed.** No other tool docstring was touched.

## Why the docstring edit does NOT move the semantic checksum
`semantic_surface_checksum` is derived from each tool's canonical **`purpose`** field, not from the docstring
body. For the source tools the `purpose` comes from a terse canonical ToolSpec override, independent of the
Python docstring prose. The corrected `assistant_get_source` docstring body therefore does not feed the
checksum. This is verified by regenerating the checksum from the live surface on BOTH trees.

## Regeneration — checksum before and after (probe: `manifest_probe.py`)
The probe builds the live tool index and calls the official `build_manifest(...)` with a pinned runtime
commit ("FIXED") and pinned `now`, so only the semantic surface can perturb the checksum. Run on two trees:

| Tree | `semantic_surface_checksum` |
|---|---|
| pristine `origin/main` `9c27839b` (no Phase A code) | `sha256:3eb81b4d765e6ab812663fd22784b8ed37054f53d9f1e1bcc5d83bb5c4bf09fc` |
| A2 HEAD `554c4b90…` (+ corrective) | `sha256:3eb81b4d765e6ab812663fd22784b8ed37054f53d9f1e1bcc5d83bb5c4bf09fc` |

**IDENTICAL.** `diff` of the two checksum lines is empty. The A2 docstring correction provably does not churn
the frozen semantic surface.

## Per-source-tool `purpose` — before vs after (no unrelated drift)
The probe also emits each source tool's canonical `purpose`. Byte-identical on both trees:

| Tool | `purpose` (origin/main == A2 HEAD) |
|---|---|
| `assistant_get_source` | `Read-only source/card/note navigation.` |
| `assistant_source_file_metadata` | `Inspect metadata for one indexed source file before a bounded read.` |
| `assistant_source_file_read` | `Indexed NAS source-file discovery.` |
| `assistant_source_file_search` | `Search indexed NAS source file contents and filenames; not for Obsidian vault notes.` |
| `assistant_source_files_list` | `Indexed NAS source-file discovery.` |

No source-tool `purpose` changed → no unrelated tool-metadata drift on the semantic surface.

## Direct / gateway parity
The parity + freshness guards that rebuild the live surface pass in the client-surface run (see
`a2-validation-client-surface.txt`): `test_manifest_schema_parity.py` and
`test_tool_manifest_freshness_guard.py` are GREEN, and the A2 suite's `test_direct_and_gateway_trust_agree`
confirms both routes funnel through one connector-service authority. Direct and gateway resolve the same
manifest.

## Official regeneration path (no hand-edited checksum)
The frozen manifest is a SQLite row recomputed from the live surface. Re-freezing means re-running the
official generation path (`pa_tool_manifest_refresh_stage` → `pa_tool_manifest_refresh_promote`, or the
registration-time `bootstrap_persisted_manifest`) — **no stored checksum was hand-edited**. Because the
regenerated `semantic_surface_checksum` is identical to origin/main (above), the frozen artifact required no
checksum change at all: the freshness guard is satisfied by the unchanged surface, not by editing a baseline.

## Conclusion
The manifest change is limited to intended semantics: one docstring corrected (bounded-excerpt truthfulness),
zero tool add/remove/rename, zero `purpose` drift, identical regenerated `semantic_surface_checksum`
(`…c4bf09fc`), direct==gateway parity intact, official generation path used, no hand-edited checksum.
