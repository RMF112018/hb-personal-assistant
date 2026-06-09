# Acceptance Checklist

## Repo / Branch

- [ ] Implementation branch created from fresh `main`.
- [ ] Main untouched.
- [ ] Working tree clean at final handoff.
- [ ] Untracked local config not committed.

## Schema

- [ ] Schema head is V45.
- [ ] V45 table exists.
- [ ] V45 table contains no raw body/prompt/response/HTML/URL/token columns.
- [ ] Guard columns exist and default to 0.
- [ ] Fresh DB migration passes.
- [ ] Copied DB migration passes.

## Raw Boundary

- [ ] Attachments excluded.
- [ ] HTML excluded.
- [ ] Quotes stripped.
- [ ] Signatures stripped.
- [ ] URLs redacted.
- [ ] Tokens/secrets redacted.
- [ ] Join/signed/download links redacted.
- [ ] Email addresses redacted by default.
- [ ] Caps enforced.
- [ ] Raw-local preview explicit only.
- [ ] Raw-local preview not JSON by default.

## Model / Enrichment

- [ ] `email_followup_raw_enrichment` route exists.
- [ ] Route is local-only.
- [ ] No cloud fallback.
- [ ] Structured output validated.
- [ ] Unknown source refs rejected.
- [ ] Hash mismatch rejected.
- [ ] Model unavailable degrades safely.

## Persistence

- [ ] Dry-run writes nothing.
- [ ] Apply requires cap.
- [ ] Apply respects cap.
- [ ] Persistence idempotent.
- [ ] V45 rows review-safe.
- [ ] No raw prompt/model response stored.
- [ ] No production DB mutation during validation.

## Daily Brief

- [ ] Pending enrichment consumed.
- [ ] Pending enrichment clearly labeled.
- [ ] Source links retained.
- [ ] No raw excerpts.
- [ ] Fallback works without enrichment.

## Evidence

- [ ] Evidence directory complete.
- [ ] Forbidden-string scan clean.
- [ ] Guard-column proof clean.
- [ ] DB-copy proof complete.
- [ ] Production DB unchanged proof complete.
