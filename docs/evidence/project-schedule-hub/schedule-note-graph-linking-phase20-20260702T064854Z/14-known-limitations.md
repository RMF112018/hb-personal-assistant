# Phase 20 Known Limitations

- Source-card links are optional conservative candidates only; never written unless recommended apply
  path includes them (currently `recommended_only=True` excludes source-card candidates from apply).
- Tag recommendations are report-only; no generated-tag convention is applied to frontmatter.
- LLM suggestions (`--suggest-links`) are report-only even when validated.
- Live vault evidence was not captured (vault path absent on capture host); dry-run attestation
  uses `17-live-vault-dry-run.json` with `skipped: true`.
- Live vault apply remains blocked without explicit `--allow-live-vault --confirm-live-vault-apply`.
- Portfolio-to-project linking requires matching `schedule_data_date` across notes.
