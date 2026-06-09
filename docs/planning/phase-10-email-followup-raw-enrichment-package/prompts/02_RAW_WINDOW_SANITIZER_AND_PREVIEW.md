# Prompt 02 — Raw Window Sanitizer and Local Preview

## Objective

Implement a bounded, redacted, no-persist raw email window builder and an explicit local-only operator preview path. This prompt must not call a model and must not persist raw packets.

## Critical Rule

Do not use or extend any existing raw context packet builder in a way that persists raw packet JSON, raw prompt text, raw response text, body HTML, URLs, or tokens. If an existing builder writes raw packet JSON for replay/audit, do not use it for this feature unless a no-persist mode is added and tested.

## Required Raw Window Behavior

The builder must:

- Accept already source-linked candidate/watch refs only.
- Resolve only email source refs.
- Load only the minimum raw email rows required for those refs.
- Exclude attachments.
- Exclude attachment text.
- Exclude `body_html`.
- Use `body_text` or text-equivalent only.
- Strip quoted replies.
- Strip signatures.
- Strip legal disclaimers where practical.
- Redact URLs.
- Redact signed/download URLs.
- Redact calendar/meeting join links.
- Redact tokens/secrets/API keys.
- Redact email addresses by default.
- Bound messages per thread.
- Bound chars per message.
- Bound total chars per enrichment call.
- Return source aliases and hashes.
- Return `raw_excerpt_hash`.
- Never write raw window content to DB, repo, evidence, logs, browser brief, or Obsidian brief.

## Default Caps

Use conservative defaults unless repo conventions suggest lower values:

```text
max_threads: 1
max_messages_per_thread: 6
max_chars_per_message: 1500
max_total_chars: 6000
max_subject_chars: 200
```

Expose caps in code/config only where needed. CLI flags may come later.

## Raw-Local Preview Behavior

Implement a preview function or service used by CLI later.

Preview must:

- Require explicit caller opt-in.
- Return bounded redacted local text.
- Be clearly marked local-only and unsafe for evidence.
- Never be included in JSON output by default.
- Never be persisted.
- Never be used in tests with real raw user content.

## Required Sanitizer Test Fixtures

Use synthetic fixtures only. Include samples with:

- quoted replies
- Outlook/Gmail separators
- signatures
- legal disclaimers
- URLs
- Microsoft Teams / Zoom style join links
- signed download URL style query strings
- fake API tokens
- fake bearer token
- fake email addresses
- fake phone numbers if sanitizer handles phones
- HTML body input proving it is ignored
- attachment metadata proving it is ignored

## Required Tests

Add tests proving:

- No raw window is built without source refs.
- Non-email refs are skipped or rejected safely.
- Attachments are excluded.
- HTML is excluded.
- URLs are redacted before model/preview surfaces.
- Join links are redacted.
- Tokens/secrets are redacted.
- Emails are redacted by default.
- Quoted text is stripped.
- Signatures are stripped.
- Caps are enforced.
- Hashes are stable.
- Preview requires explicit opt-in.
- Preview object is marked as non-persistable.

## Stop Conditions

Stop if:

- Existing raw storage cannot be read without side effects.
- Sanitizer cannot reliably block URLs/tokens.
- Any raw preview path writes to log/evidence/test snapshots.
- Tests require real emails.

## Commit

After tests pass:

```bash
git add <raw window files> <tests>
git commit -m "feat(email): add bounded raw follow-up window sanitizer and local preview"
```

## Exit Criteria

- Raw window builder implemented.
- Sanitizer tests pass.
- Raw preview is explicit, local-only, redacted, bounded, and non-persisted.
- Commit created.
