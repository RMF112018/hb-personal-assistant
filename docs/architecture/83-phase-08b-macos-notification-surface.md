# 83 — Phase 08B: macOS Notification Surface (Prompt 11)

**Status:** Implemented (additive). Schema **V32 → V33** (one new table); package stays `1.3.0`.
**Baseline:** atop `6a89de0` (08B Prompt 10; 08A closeout `954a518` is ancestor).
**Scope:** A dry-run-by-default agent that previews and — on apply, *real-but-policy-gated like the
Prompt-04 launchd install* — emits a **local** macOS Notification Center banner, plus a V33
notification-receipt ledger and a proof-backed `daily_brief_notification` gate. `automation_execution`
stays the only deferred 08B gate.

## Context

The durable delivery handoff carries `NotificationSummary` — a *data-only* summary (counts +
`channel="local_only"`, `emitted=False` with a validator that **rejects** `emitted=True`): the
long-stubbed "future macOS notification" hook. **No notification was emitted anywhere in the repo.**
This prompt builds that surface as a new, explicitly-bounded path — it does **not** touch the
data-only `NotificationSummary` guardrail (`emitted` stays rejected on that model). A local
Notification Center banner is **not** external delivery (no email/Slack/Teams/SMS/push/webhook/Graph
`sendMail`) — it is the explicit objective.

## Design

New module `construction/second_brain/daily_brief_notify.py` (same P09/P10 agent shape; injects
`db_path`/`now`/`notifier`/`policy_emit`; reuses `read_daily_brief_handoff`,
`read_latest_daily_brief_runs`):

- `build_notification_text(summary)` — redacted (title, body) from the handoff `NotificationSummary`
  ("{attention} priority · {review} review · {warning} warnings · {project} projects"); counts only.
- `_default_macos_notifier(title, body)` — `osascript -e 'display notification …'` via
  `subprocess.run([...], capture_output=True, text=True, check=False)` (no `shell=True`; AppleScript-
  escaped; darwin-guarded). Mirrors `launchd_scheduler._default_launchctl_runner`. **Injectable** so
  tests never fire a real banner.
- `_policy_emit_enabled(seed)` — reads seed `daily_brief_notification.emit` (default `False` =
  fail-closed). Mirrors `launchd_scheduler._policy_dry_run_only`.
- `evaluate_daily_brief_notification` (read-only) → `NOTIFY_NEVER_GENERATED` / `_BLOCKED` / `_STALE` /
  `_ALREADY_EMITTED` / `_ELIGIBLE` over V26 runs + V33 receipts.
- `run_daily_brief_notification_agent(mode=…, notifier=…, policy_emit=…, emit_receipt=…)`: **dry-run
  default** previews the would-be banner, writes nothing; **apply** (only when eligible): if policy
  emission is off → `NOTIFY_DISABLED_BY_POLICY` (no `osascript`, no receipt), else call
  `notifier(title, body)` → `NOTIFY_EMITTED` + a V33 receipt (counts + title hash). The optional V28
  agent receipt (`agent_id='daily_brief_notification_agent'`) is emit-gated.
- `build_daily_brief_notification_proof()` drives the gate across never-generated / blocked / stale /
  eligible (dry-run) / disabled-by-policy (apply, emit off — notifier NOT called, no receipt) /
  emitted (apply, emit on + fake notifier) / already-emitted, with a values-only no-raw scan.

### Schema (V33) / safety / gate / policy / CLI

- `migrator.py`: `LATEST_SCHEMA_VERSION 32 → 33`; new `daily_brief_notification_receipts` — metadata
  only (counts + a title **hash**; raw text never stored), **`CHECK(channel = 'local_macos')`** pins
  the channel, `mode IN ('dry_run','apply')`, FK to `daily_brief_runs`, the 9 standard `CHECK(col =
  0)` guards. Registered in `safety._PHASE_08A_TABLES`.
- `data_quality.py`: new `daily_brief_notification` proof-gate → **pass**; phase-08b-gates → **14
  pass / 0 warning / 0 fail / 1 deferred**.
- Policy seed + both contracts updated with the seven `NOTIFY_*` reason codes + the gate; lifecycle
  `table_count 149 → 150` + the new table entry (`v: V33`). The seed `daily_brief_notification.emit`
  defaults to `false` (fail-closed).
- CLI: `second-brain automation notify-status` (read-only) + `notify` (apply-capable, **dry-run
  default**, `--brief-date`, `--emit-receipt` off by default; exit 0/3/2).

## Guardrails

Local only — the sole channel is the macOS Notification Center, pinned by `CHECK(channel =
'local_macos')`; no email/Slack/Teams/SMS/push/webhook/Graph `sendMail`. Dry-run is the default; apply
is fail-closed behind `daily_brief_notification.emit` (default off → `NOTIFY_DISABLED_BY_POLICY`, no
`osascript`). Receipts store only counts + a title hash (never raw text); 9 guard `CHECK(col = 0)`
columns. No external writeback/delivery. Phase 08A guardrails preserved (phase-08a-gates 8/1/0/3;
no-writeback proof passes at schema 33).

## Known limitations / next

- `automation_execution` stays deferred — the final executor + morning-orchestrator wiring (the notify
  surface is ready to be wired as an optional step).
- Real `osascript` emission only fires on a Mac with `daily_brief_notification.emit=true`; the suite
  always injects a fake notifier and never fires a banner.
- Apply writes the V33 receipt only on actual emission (the notify ledger); the V28 receipt is
  emit-gated. Idempotency keys on a prior `emitted` receipt for the brief run/date.
