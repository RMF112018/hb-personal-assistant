# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

## 5. Obsidian Vault Planning and Implementation Package Governance

- Vault root: `/Users/bobbyfetting/Documents/Obsidian Vault/Work/HB Personal Assistant/`
- Repo root: `/Users/bobbyfetting/hb-personal-assistant`
- Source-of-truth rule: Repository code, tests, runtime behavior, and repo evidence are authoritative over planning notes.
- Package lifecycle states: `Active`, `Closed`, `Deferred`, `Superseded`.
- Preflight rule: Before modifying or removing package sources, verify migration prerequisites, manifest status, and registry coverage.
- Migration verification rule: Package migration is valid only when manifest coverage, payload counts, and pre-metadata hash verification pass; post-metadata changes must be declared.
- Closure-note rule: Any `Closed` package must have `CLOSURE_NOTE.md` or be explicitly marked pending closeout.
- Registry update rule: Lifecycle changes must be reflected in `09_Implementation_Packages/Package Registry.md` and related migration manifests.
- Deferred scope rule: Deferred external blockers may be documented without reclassifying evidence bundles as lifecycle packages.
- Conflict rule: If vault package instructions conflict with repo truth, stop and report conflict before patching.
- Evidence rule: `docs/evidence/**` stays in repo and is referenced; evidence bundles are not lifecycle-classified implementation packages.
- No-secret rule: Never copy credentials, tokens, or sensitive runtime material into governance notes.
- No-plugin rule: Governance instructions must remain usable without Obsidian plugin dependencies.
