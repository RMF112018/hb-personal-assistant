# 01 — N8C-1 Baseline & Carry-forward

## N8C-1 state (verified read-only preflight)
- N8C-1 implementation committed locally as **`acd22926`** on branch
  `ops/nas-second-brain-n8c-01-neutral-graph-20260705T185844Z`, base `e80f3729`. Working tree clean.
- **Not on remote** (`git branch -r --contains acd22926` empty) → N8C-2 branches locally.

## Evidence-staleness correction (revision 1 — done before N8C-2)
The N8C-1 evidence files `00-closeout.md` and `18-git-status.md` were written before the commit landed
and still read "No commit made / Not committed". They were corrected to record: committed locally as
`acd22926`, base `e80f3729`, tree clean, **not pushed**. That correction is a **separate commit**
`c454a581` on the N8C-1 branch — deliberately **not** folded into any N8C-2 commit. N8C-2's base is
therefore `c454a581` (= `acd22926` + the evidence correction).

```
c454a581  N8C-1 evidence: correct commit-state metadata (was stale "no commit made")
acd22926  N8C-1: neutral second-brain foundation (naming, AI-Outputs frontmatter, local-summary dual-read)
e80f3729  (origin/main) nas-mcp: add OAuth 2.1 second credential ...
```

## Carried-forward N8C-1 rules (preserved by N8C-2)
No new `hb_*` generated/public branding; live MCP tool names unchanged; no broadened remote write; no
raw SQL / arbitrary filesystem exposure; no raw/import DB mutation; frontend backend-mediated; Qwen
deferred; neutral metadata going forward. N8C-2 adds only read-only internal functions.

## Environment
Python venv at `<repo>/.venv` (the main `hb-personal-assistant` checkout, shared across worktrees);
tests run with `PYTHONPATH=src:subrepos/construction-financial-review/src`.
