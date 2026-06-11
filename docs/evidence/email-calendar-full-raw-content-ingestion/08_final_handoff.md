# 08 — Final Handoff

## Branch / commits

```text
branch:    fix/email-calendar-full-raw-content-ingestion
Pass 1:    3e50fd7e  (schema V49 + ingestion hardening + structured projection layer + fixtures)
Pass 2:    7a663951da6ef32f4767a252cf4cd766e3bb6f51  (consumer read models + CLI + redaction/access audit + evidence + runbook + arch)
```

## Schema head

```text
before:  48
after:   49   (additive only; idempotent; V1-V48 untouched)
```

## Implementation summary

Pass 1 captured full raw email/calendar content with source-quality provenance and built the final
structured projection layer (registry → engine → coverage) with mechanical zero-unmapped proof.
Pass 2 rewired every consumer (email/calendar endpoints, meeting prep, model-context packets,
follow-up windows, relationship extraction, retrieval) through a single precedence-aware read model
so the structured layer is always preferred over raw-landing / legacy metadata, added the
`email-calendar raw` CLI/status surfaces, and proved no outbound raw leakage.

## Tests run

```text
tests/test_email_calendar_full_raw_content_ingestion.py ......... PASS (Pass 1)
tests/test_email_calendar_structured_projection_remediation.py .. PASS (Pass 1)
tests/test_email_calendar_projection_completeness.py ............ PASS (Pass 1)
tests/test_email_calendar_consumer_read_models.py ............... PASS (Pass 2, 14 tests)
ruff (touched modules) .......................................... PASS
mypy (email_calendar package + cli) ............................. PASS
regression subset ............................................... only 2 pre-existing env failures
  (test_calendar_event_indexing raw-flag; test_retrieval embedder 768-vs-64) — both fail on the
  clean baseline with this work stashed; NOT introduced by this work.
```

## DB-copy validation summary

```text
production sha256/mtime unchanged (Pass 1 + Pass 2): TRUE
/tmp copy: 117 calendar raw -> 117 structured (+1262 attendees); 1 email raw -> 1 structured (+2)
unmapped primary = 0, unmapped nested = 0 for every family with raw rows
consumers select the structured layer for all 118 production rows (tier structured_legacy until
operator re-ingest reclassifies full-body rows to structured_full)
```

## No-leak proof summary

```text
email/calendar no-raw-leak scan over evidence + captured CLI output: 0 findings
read-model objects, meeting-prep sections, retrieval results, projection receipts: no body/join URL
```

## Consumer before/after

```text
consumer                  | before                                  | after
email/calendar endpoints  | raw attach, no source marker            | + _selected_source / source_quality (structured preferred)
meeting prep              | persisted raw body + join URL in section| structured-sourced; flags + roles only (no body/join URL)
model context packets     | raw via endpoints                       | + structured_projection_preferred + source_quality_distribution
relationship extraction   | raw thread×event, confidence only       | structured-backed preferred + source-quality tagged
retrieval                 | no email/calendar helper                | retrieve_email_calendar_structured (redacted, structured-ranked)
follow-up window          | raw rows                                | + structured source-quality tag
```

## Production runbook path

`docs/evidence/email-calendar-full-raw-content-ingestion/operator_production_runbook.md`
(documented; NOT executed — production rollout is operator-controlled).

## Architecture

`docs/architecture/email-calendar-raw-structured-projection-layer.md`

## Known limitations / deferred

- Production raw rows are `metadata_only` until an operator raw re-ingest (runbook step 2) captures
  full bodies and reclassifies them to `graph_full_body` / `graph_full_event_body`.
- Two pre-existing env-dependent test failures persist (real Ollama dimension; raw-policy-on dev env).

## Exact commands Bobby should run next

```bash
git show 3e50fd7e --stat            # Pass 1
git show 7a663951da6ef32f4767a252cf4cd766e3bb6f51 --stat          # Pass 2
.venv/bin/python3.12 -m pytest tests/test_email_calendar_*.py -q
# then, when ready for real data, follow operator_production_runbook.md (dry-run first)
```
