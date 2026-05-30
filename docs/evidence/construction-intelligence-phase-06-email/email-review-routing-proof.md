# Email Review Routing & Encrypted-Body Eligibility — Proof

Phase 06 Prompt 10 · **local-only** (no Graph, no mailbox) · evidence-safe (redacted).

Routing is conservative; categories are **signals, not determinations**. Plaintext body
is never fetched, stored, logged, or emitted — this prompt only computes *eligibility*.

## Sensitive review-category matrix (23)

Source of truth: `src/hb_assistant/construction/email/review_categories.py` (mirrored to
`resources/config/email_sensitivity_review_categories.json`; a drift-guard test keeps them
in sync). The first 19 reproduce `attachment_analyzer.SENSITIVITY_KEYWORDS` exactly; the
last 4 are Prompt 10 additions. Every category permits encrypted capture **but requires
review first** (policy: `encrypted_body_requires_review_for_sensitive`).

| Category id | Level | Encrypted capture | Review first |
|---|---|---|---|
| legal_correspondence | high | allowed | required |
| privileged_or_confidential_markers | high | allowed | required |
| claims | high | allowed | required |
| default_or_termination_language | high | allowed | required |
| disputes | high | allowed | required |
| injuries | high | allowed | required |
| incidents | high | allowed | required |
| medical_detail | high | allowed | required |
| personnel_or_hr | high | allowed | required |
| liquidated_damages | high | allowed | required |
| contracts | medium | allowed | required |
| change_orders | medium | allowed | required |
| notices | medium | allowed | required |
| insurance_or_bonding | medium | allowed | required |
| pay_applications | medium | allowed | required |
| invoices | medium | allowed | required |
| lien_releases | medium | allowed | required |
| delay_or_time_extension_language | medium | allowed | required |
| additional_compensation_language | medium | allowed | required |
| confidential_bid_or_estimate *(new)* | high | allowed | required |
| owner_directive *(new)* | medium | allowed | required |
| subcontractor_default *(new)* | high | allowed | required |
| schedule_recovery_or_acceleration *(new)* | medium | allowed | required |

## Encrypted-body eligibility logic (`review_router.py`)

For each project-matched message in the bounded lookback window:

- **eligible_for_full_body_fetch** = project-matched **and** policy
  `full_body_storage_allowed` **and** folder in-scope (not deleted/junk/drafts) **and**
  within the per-run cap `max_full_body_fetch_per_run` (100). Old messages (outside
  lookback) are excluded up front.
- **eligible_for_encrypted_body_storage** = eligible fetch **and** policy mode
  `encrypted_text_vault`; otherwise `encrypted_storage_mode = "not_allowed"`.
- **review_required_before_body_use** = any sensitive category present **or**
  low-confidence project match (`< low_confidence_threshold` 0.75) **or** the stored
  match already flagged review.
- **plaintext_body_persistence_allowed** is structurally `False` everywhere — no field or
  flag is ever set to allow it.

Sensitive / low-confidence messages are routed to `email_review_queue`; each routed row
carries the V13 decision metadata (`body_capture_eligible`,
`encrypted_body_capture_allowed`, `review_required_before_body_use`,
`body_capture_decision_json`).

## Live validation — `graph mail review-queue --project tropical --lookback-days 30 --dry-run --json`

Exit 0, `ok: true` (local-only; no Graph). Captured (redacted) in
[`email-review-routing-dry-run.json`](./email-review-routing-dry-run.json):

```json
{
  "command": "graph mail review-queue",
  "ok": true,
  "project_key": "tropical",
  "project_number": "23-435-01",
  "lookback_days": 30,
  "dry_run": true,
  "persisted": false,
  "policy_version": "phase06-email-active-v1",
  "messages_considered": 40,
  "routed_to_review": 7,
  "review_items_enqueued": 7,
  "body_capture_eligible_count": 40,
  "encrypted_body_storage_eligible_count": 40,
  "review_required_before_body_use_count": 7,
  "categories_seen": {"contracts": 3, "privileged_or_confidential_markers": 1}
}
```

40 tropical-matched messages considered (all within the 30-day window and in-scope
folders → 40 body-capture eligible, 40 encrypted-storage eligible, none plaintext); 7
routed to review (sensitive categories + low-confidence matches).

Representative redacted sample (no subjects/addresses; `message_ref` is a hash):

```json
{
  "message_ref": "46389cde01f4d6be",
  "project_match_confidence": "medium",
  "sensitivity_categories": [],
  "review_required": false,
  "body_capture_eligible": true,
  "encrypted_body_capture_allowed": true,
  "encrypted_storage_mode": "encrypted_text_vault",
  "plaintext_body_persistence_allowed": false
}
```

Persisting (`--no-dry-run`) enqueues `email_review_queue` rows with the decision metadata;
re-running is idempotent (queue count stable — `INSERT OR IGNORE` on
`(message_id, category, reason)`). Persisted-row categories observed on the pilot DB
included `contracts`, `privileged_or_confidential_markers`, `pay_applications`,
`lien_releases`, and `low_confidence_project_match`.

## No plaintext / no mutation proof

- Leak scan of the dry-run JSON: no `access_token`, no `Bearer `, no `decrypted body`
  marker, and `plaintext_body_persistence_allowed` is `false` on every sample.
- `body_capture_decision_json` persisted rows contain no plaintext body (verified: no
  `plaintext` truthiness in any stored decision).
- New modules `review_categories.py` + `review_router.py` are auto-scanned by
  `tests/test_email_body_security.py` (no write verbs, no `createReply/forward/sendMail/
  move/copy/markRead`, no `raw_body/body_html/body_plaintext`) and
  `tests/test_mutation_lockout.py` — clean.
- Migration V13 is additive `ALTER TABLE … ADD COLUMN` only; no plaintext-body column is
  added and `email_message_body_vault_refs.CHECK(plaintext_persisted = 0)` /
  `email_messages.CHECK(full_body_persisted = 0)` remain in force.

## Validation commands

- `ruff check .` → All checks passed.
- `mypy src` → Success (127 source files).
- `python -m compileall -q src tests` → OK.
- `pytest -m "not integration and not live and not manual" --ignore=tests/test_automation.py`
  → all passing (incl. the new `test_review_categories.py` + `test_review_router.py` and
  the migration version-assert bumps to V13).
- `tests/test_automation.py` → 4 pre-existing date-driven (weekend) failures, unrelated.

## Stop conditions — none triggered

No mailbox mutation path; no plaintext body persistence; additive ADD-COLUMN migration
only; read-only/local-only throughout.
