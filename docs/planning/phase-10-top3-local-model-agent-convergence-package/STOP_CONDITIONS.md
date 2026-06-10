# Stop Conditions

The local agent must stop immediately and provide a partial handoff if any condition below is true.

## Privacy / leakage

- Raw email body, document body, calendar body, Procore payload, model prompt, model response, unsafe HTML, credential-shaped string, full URL, signed/download/join link, or private payload appears in repo files, tests, evidence, logs, browser proof, Obsidian proof, or status proof.
- Any evidence command prints raw private content.

## Writeback / mutation

- Production DB changes during validation.
- Any Microsoft Graph writeback path is invoked.
- Any email send or draft path is invoked.
- Any calendar mutation path is invoked.
- Any Procore writeback path is invoked.
- Any MCP raw exposure path is invoked.
- Any external writeback path is invoked.

## Model safety

- Cloud model route or fallback is added.
- Local model output can create accepted facts without source-link validation.
- Unsourced bullets survive into the final brief.
- Raw prompt/response is persisted.

## Apply safety

- Any apply path lacks `--max-*` or equivalent cap.
- Email raw enrichment can run without source links.
- Email raw enrichment can persist raw body/prompt/response.
- Scheduler install defaults to browser auto-open.

## Validation

- New tests fail.
- Safety scan fails.
- Guard columns become nonzero.
- Output path safety guard fails.
- Final residual-work audit cannot prove all package objectives are complete.
