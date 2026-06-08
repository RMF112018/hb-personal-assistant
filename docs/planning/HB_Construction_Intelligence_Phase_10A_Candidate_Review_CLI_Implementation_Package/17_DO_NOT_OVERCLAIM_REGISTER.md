# 17 Do Not Overclaim Register

Do not claim any of the following unless proven by local validation:

- The review CLI has been tested against the populated dev DB.
- The current persisted count is exactly 21.
- The schema migration ran on production.
- Snoozed candidates are correctly hidden from every UI surface.
- Accepted candidates are safe for automation.
- Candidate semantic quality is solved.
- Review events historically captured prior actions before this update.
- The frontend consumes review statuses.
- Any external system was updated.

Allowed claims after implementation and validation:

- The CLI can list/show/summarize persisted candidates.
- The CLI can update local review status.
- The CLI writes local review events.
- Outputs are redacted/safe according to tests.
- No-raw/no-writeback proofs passed.
