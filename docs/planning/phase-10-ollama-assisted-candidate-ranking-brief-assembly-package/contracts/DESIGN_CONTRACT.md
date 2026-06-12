# Design Contract — Ollama-Assisted Feedback-Calibrated Ranking

## Authority hierarchy

1. Raw-safety gates
2. Source-ref requirements
3. Lifecycle/review/suppression/merge/snooze state
4. Deterministic eligibility filters
5. Deterministic score
6. Aggregate feedback calibration
7. Local Ollama advisory ranking/grouping/narrative

The model is last in the hierarchy and cannot override any higher layer.

## Model input contract

The model sees only a compact JSON packet of aliases and redacted structured fields. It never sees raw body text, raw Procore payloads, full URLs, tokens, email addresses, or local paths.

## Model output contract

The model may return:

- bounded priority advice
- grouping labels
- duplicate/similarity hints
- `why_this_matters_redacted`
- short narrative assembly suggestions

The model may not return:

- new candidates
- lifecycle changes
- source-ref changes
- external writeback recommendations
- raw or private content

## Fallback contract

If the model layer fails, withholds, degrades, or is disabled, the deterministic ranked brief must still render. Status must say exactly why the model layer did not contribute.
