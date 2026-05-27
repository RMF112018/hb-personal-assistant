# 03 — Hardening Implementation Plan

## Patch Theme 1 — Morning Run Action Extraction Truth

Problem to verify: `MorningRunOrchestrator` may claim to wire action extraction but call a non-existent `ActionService.extract_candidates()` method instead of `ActionService.extract()`.

Required result:

```python
actions = ActionService(store=self.store).extract(dry_run=dry_run)
```

Acceptance:

- seeded local signals produce nonzero actions;
- dry-run does not persist action items/source links;
- apply mode persists idempotently;
- stage counts accurately reflect extraction count.

## Patch Theme 2 — Dry-Run Semantics

Required policy:

```text
Dry-run does not mutate Microsoft 365, Obsidian notes, action_items, source_records, source_links, files, parser_outputs, or generated work products.

Dry-run may write local run-ledger/evidence records only when explicitly documented.
```

Acceptance:

- CLI notes match policy;
- tests prove dry-run does not persist business objects;
- evidence states whether run ledger/evidence writes occur.

## Patch Theme 3 — Obsidian `written_to_note` Provenance

Required result:

- apply path creates `source_links.link_type = written_to_note`;
- dry-run reports what would link without persisting it;
- tests verify both paths;
- source IDs are valid and traceable.

## Patch Theme 4 — Workstream Context Body Mentions

Required result:

- `WorkstreamContextBuilder` populates `mentions`;
- mentions are bounded/redacted;
- brief/action context can consume mentions;
- tests cover empty and populated mention states.

## Patch Theme 5 — Validation Scope Reduction

Required result:

- reduce Ruff/mypy exclusions for MVP-critical modules only;
- avoid broad lint/type debt cleanup outside current scope;
- document remaining exclusions and next shrink path.

Initial strict candidates:

```text
src/hb_assistant/actions
src/hb_assistant/automation
src/hb_assistant/obsidian
src/hb_assistant/retrieval/context.py
src/hb_assistant/cli/actions.py
src/hb_assistant/cli/run.py
tests/test_actions*.py
tests/test_automation*.py
tests/test_obsidian*.py
```

## Patch Theme 6 — MVP Evidence Harness

Required result:

- deterministic local fixture/seeding path;
- repeatable dry-run and apply proof;
- idempotency proof;
- sensitive scan proof;
- known limitations doc.
