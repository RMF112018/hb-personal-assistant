# Copied DB CPM / trend audit

DB: `/tmp/hb-pa-schedule-ux-final/hb-pa-schedule-ux-20260702T160500Z.sqlite`

## API payloads
- schedule-asof-2026-06-22.json: as_of=2026-06-22 svk=tropical|1069|2026-05-26 08:00 cpm_available=False
- schedule-asof-2026-06-29.json: as_of=2026-06-29 svk=tropical|1071|2026-06-23 08:00 cpm_available=True
- baselines.json: as_of=2026-07-03
- controls-asof-2026-06-22-prior-update.json: as_of=2026-06-22
- controls-asof-2026-06-29-prior-update.json: as_of=2026-06-29
- cpm-summary-asof-2026-06-22.json: svk=tropical|1069|2026-05-26 08:00 available=false
- cpm-diagnostics-asof-2026-06-22.json: svk=tropical|1069|2026-05-26 08:00
- cpm-summary-asof-2026-06-29.json: svk=tropical|1071|2026-06-23 08:00 available=true (all run types present)
- cpm-diagnostics-asof-2026-06-29.json: svk=tropical|1071|2026-06-23 08:00 (52 diagnostics)

## SQL inventory

- import tropical|TWNU07|2025-08-07T08:00:00 activities=1177 created=2026-06-22 10:05:20
- import tropical|TWNU16|2026-01-29T08:00:00 activities=1420 created=2026-06-22 10:05:20
- import tropical|TWNU18|2026-05-26T08:00:00 activities=1378 created=2026-06-22 13:47:28
- import tropical|24836|2026-06-23 08:00 activities=1507 created=2026-06-24 12:28:28
- import tropical|TWNU19|2026-06-23T08:00:00 activities=1507 created=2026-06-26 11:31:36
- import tropical|815|2025-08-07 08:00 activities=1177 created=2026-06-28 09:34:05
- import tropical|851|2025-11-28 08:00 activities=1404 created=2026-06-28 09:34:27
- import tropical|957|2026-01-29 08:00 activities=1420 created=2026-06-28 09:34:41
- import tropical|1069|2026-05-26 08:00 activities=1378 created=2026-06-28 12:02:46
- import tropical|1071|2026-06-23 08:00 activities=1507 created=2026-06-28 12:03:10

## Recompute gate
SQL shows CPM runs present for resolved versions; **no recompute** performed.
