# 10 — `/tmp` DB-Copy Validation

All apply/idempotency checks ran on a `/tmp` copy of the plain-root production DB. The production
DB was never opened for write by any slice code path; its SHA-256 is identical before and after.

## Production-safety proof

- Production DB: `~/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite`
- Copy: `/tmp/hb-phase10-candidate-lifecycle-validation-20260611-154632/validation-copy.sqlite`
- Active-writer context: a `scheduler run daily-source-refresh --environment dev --loop` process is
  running, but `--environment dev` pins the `(Dev)` app-support root, not the plain root validated
  here. dbeaver holds a read handle. Read-only audit used `?mode=ro`; all writes targeted the copy.
- **Production SHA-256 before:** `d0c3e52a15b9dbdf65174f9347e1c596ed97ca2098e167902d94406a9ceccdb7`
- **Production SHA-256 after:**  `d0c3e52a15b9dbdf65174f9347e1c596ed97ca2098e167902d94406a9ceccdb7`
- **Unchanged:** YES

## Migration

- `LATEST_SCHEMA_VERSION`: 50
- Applied on copy: 50
- Re-applied (idempotent): 50
- Integrity check before: `ok`
- Integrity check after: `ok`

## Lifecycle behavior on the copy (synthetic rows seeded into the copy only)

- Lifecycle events: 6
- Idempotency replay (accept/reject/merge re-issued): **no new events** (count stable)
- Lifecycle counts by state: accepted 1, rejected 1, snoozed 1, closed 1, merged 1
- Review queue total subjects: 7
- Review queue visible (default): 1 (the source-missing row, withheld/degraded — honestly surfaced)
- State counts (all): accepted 2, closed 1, merged 1, rejected 1, snoozed 1, source_missing 1
- Accepted task count: 1 (promotion idempotent)
- **Guard-column sum across the 3 V50 lifecycle tables: 0**
- Usefulness stage contradictions: `["lifecycle_source_ref_coverage_below_100"]`
  (correctly flags the deliberately source-missing surfaced row)
- Feedback counts: total_reviewed 5, accepted 1, rejected 1, snoozed 1, merged 1, closed 1,
  source_missing 1

## Source / project coverage

- Source-ref coverage gate enforced at acceptance + promotion (source-missing actionable subjects
  blocked; the one source-missing row is surfaced as `source_missing`, never silently accepted).
- Project-key coverage: `project_review_required` surfaced for null-project candidate families
  (precedence-masked only when a higher-precedence state such as snooze applies).

## Result

PASS — production DB unmutated, migration additive + idempotent, guard sum 0, integrity ok,
lifecycle operations idempotent on replay.
