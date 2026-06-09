# Raw-Local Preview — Synthetic Proof

All content here is synthetic. Demonstrates the preview gate; no real raw email content shown.

- requires explicit opt_in=True: refused without it = **True**
- preview.is_persistable = **False**
- CLI gate: `--show-raw-local` requires `--dry-run` + `--no-json`; refused with `--json`/`--apply`
- banner: `⚠ RAW-LOCAL PREVIEW — local terminal only. Bounded + redacted. NEVER copy into evidence, docs, logs, commits, or the daily brief. Not persisted.`
- preview is terminal-only, never written to JSON / evidence / logs / brief
