# Render Labeling — banners + Model Enriched Intelligence

## Banners
- `daily_run_html.py`: added a `deterministic_fallback` param + status-text/`_STATUS_CLASS` entry for
  `deterministic_success_synthesis_degraded` (class `ok`). When `deterministic_fallback` is true the
  degraded banner is replaced by an operator-usable one: "✓ Deterministic source-linked brief
  published. Local-model synthesis was degraded: <reason>. This brief is operator-usable because the
  deterministic usefulness gate passed." The old "Partial — synthesis degraded or a stage failed" /
  "NOT counted as successful" wording no longer appears on a deterministic-fallback brief.
- `daily_brief_llm_synthesis.py`: new `render_deterministic_fallback_markdown` (operator-usable
  Obsidian/markdown banner), distinct from `render_degraded_markdown` (kept for usefulness-failed).

## Model Enriched Intelligence
When synthesis degraded, `run_daily_local_agent` forces the MEI envelope to withheld
(`available=False`, `degraded=True`, `withheld_reason=synthesis_degraded:<reason>`) and relabels it
`Source-Linked Deterministic Brief`. `status_block` now surfaces the overridden label. MEI is never
shown as `available=true, degraded=false` while synthesis is degraded; the raw-free pending rows still
render under the deterministic label.

## DB-copy proof (verbatim presence checks on the rendered fallback HTML)
```
operator-usable banner: 1
MEI relabeled (Source-Linked Deterministic Brief): 1
old "Partial — synthesis degraded or a stage failed": 0
old "NOT counted as successful": 0
obsidian operator-usable banner: 1
```
