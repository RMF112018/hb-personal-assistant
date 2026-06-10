# Reference — CLI Contract

The final CLI surface should be coherent and backward-compatible.

## Daily run

Required behavior:

```text
hb-assistant second-brain daily-run run
```

Default behavior:
- Model Enriched Intelligence: on
- Browser generation: on unless explicitly disabled
- Browser auto-open: off
- Email raw enrichment: eligible in apply mode with caps and readiness gates
- Dry-run: no persistence

Required disable flag:
- `--no-model-enriched-intelligence`

Recommended positive flag / alias:
- `--model-enriched-intelligence`

Existing flags like `--with-intelligence` may be retained as backward-compatible aliases, but help text must not imply old behavior.

## Scheduler install/status

Install preview and status must reveal:

- schedule time
- weekdays-only behavior
- catch-up-on-wake behavior
- executable readiness
- working directory readiness
- log directory readiness
- Model Enriched Intelligence enabled/disabled
- email raw enrichment enabled/disabled
- browser generation enabled
- browser auto-open disabled
- vault brief target redacted
- DB path redacted if provided

## Email raw enrichment

Required command or subcommand:

```text
hb-assistant second-brain follow-up-watch enrich-readiness
```

or equivalent, provided the README/runbook documents it.

The readiness report must include:
- accepted task/commitment count
- source-linked accepted count
- email-source-linked accepted count
- raw-content-available count
- eligible count
- skip counts by reason
- guardrails
