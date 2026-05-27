# 09 — Source Truth Checklists

## Code-Truth Checklist

- [ ] `hb-assistant` CLI entry point resolves.
- [ ] `actions` group is registered.
- [ ] `ActionService.extract()` is the service method used by orchestrator.
- [ ] `extract_candidates()` remains lower-level extractor only.
- [ ] `upsert_action_item()` preserves completed status.
- [ ] `link_action()` is idempotent.
- [x] `written_to_note` is allowed and tested.
- [x] `WorkstreamContextBuilder.mentions` is populated.
- [ ] `run morning` classifies Graph blocker correctly.
- [ ] `run morning` local stages continue despite missing Graph consent.

## Evidence Checklist

- [ ] Repo-truth evidence captured.
- [ ] Validation output captured.
- [ ] Action extraction proof captured.
- [ ] Morning dry-run proof captured.
- [ ] Obsidian provenance proof captured.
- [ ] Idempotency proof captured.
- [ ] Sensitive scan proof captured.
- [ ] Known limitations documented.

## Safety Checklist

- [ ] No M365 writeback.
- [ ] No app-only mail/calendar runtime.
- [ ] No full bodies.
- [ ] No full files.
- [ ] No secrets.
- [ ] No private Obsidian content.
- [ ] No raw Graph payloads in evidence.
