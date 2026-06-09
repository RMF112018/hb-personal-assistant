# Live Model Performance Proof

Live `mistral-nemo:12b` via local Ollama, `/tmp` Dev DB copy (20 candidates, 2026-06-09). Metrics only.

## Standalone `daily-brief intelligence` (live, dry-run)

| Run | status | route → terminal | fallback | schema_valid | bullets_kept | source_link_coverage | usefulness | alias_mapping_used | latency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Pre-apply | ok | brief_synthesis → brief_synthesis | false | true | 12 | 1.0 | 1.0 | true | ~53s |
| Post-apply | ok | brief_synthesis → brief_synthesis | false | true | 6 | 1.0 | 0.94 | true | ~35s |

Both runs enriched **on the first attempt with no fallback** — the decisive change from the prior
evidence (which recorded run-to-run withhold variance and 142–218s latencies). The short-alias scheme
makes source-linking reliable; the `mode="before"` `executive_catchup` coercion eliminates the
spurious `schema_invalid`.

## Honest notes

- Latency for a 12B local synthesis call is ~35–55s on this host; well within the profile's 180s
  timeout. No fallback was needed once the schema-shape bug was fixed.
- `usefulness_score` is computed from section coverage on the redacted candidate set; it is advisory.
- This is a single-host, single-day live sample. The eval harness (`local-model eval --live`) remains
  the tool for repeatable cross-profile quality measurement.
