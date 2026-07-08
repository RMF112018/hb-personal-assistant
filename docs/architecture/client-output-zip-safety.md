# Client Output ZIP Safety (N8C-24)

ZIP is higher-risk than plain documents: it can carry traversal/absolute member paths, symlinks, encrypted
members, denied filenames, or decompression bombs. N8C-24 validates every ZIP **before** writing it and
**never extracts**.

## Validation (`client_output_zip.validate_zip_payload`)

Runs before a ZIP is written (at stage time). Hard-fails (`ZipValidationError`, nothing written) on:

- payload larger than `max_client_output_file_bytes`;
- not a valid ZIP;
- member count > `max_client_output_zip_members`;
- any member with an absolute path (`/…`, `C:\…`);
- any member path containing `..`, `\`, `.git/`, `.obsidian/`, `__macosx`, `.ssh/`, or credential fragments;
- any member with an executable/script extension (`.sh .command .app .exe .dmg .pkg .bat .ps1 .jar .dylib`);
- any encrypted member (general-purpose bit 0 set);
- any symlink member (unix mode `S_IFLNK` in `external_attr`);
- total uncompressed size > `max_client_output_zip_uncompressed_bytes` (bomb guard).

On success it returns a bounded summary: member count, compressed/uncompressed bytes, a bounded member
preview, and warnings. This summary is recorded on the commit receipt (`## ZIP Validation`).

## ZIP write modes

- `direct_base64_zip` — the client supplies base64 ZIP bytes; validated then written.
- `assembled_zip_from_staged_outputs` — assemble a ZIP from already-committed outputs; member names are
  sanitized and the assembled bytes are re-validated through the same validator.

## Never exposed

There is **no** tool or code path that extracts a ZIP, executes ZIP contents, follows ZIP symlinks, or
writes files from a ZIP outside the output root. `pa_output_zip_inspect` lists members only (bounded). A test
asserts no `extract`-named function exists in the ZIP module.
