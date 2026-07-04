# 07 — First-Indexing Dry-Run — DEFERRED

## Tool + safety confirmation
`scripts/obsidian_source_first_indexing_dryrun.py` — confirmed strictly read-only from source:
- `--db-path` is "Accepted but never written (dry-run is read-only)".
- `os.walk` + deterministic classification only; **no DB writes, no event enqueue, no queue drain, no card
  generation, no summaries, no backend start**; symlinks recorded, never followed.

## Why deferred (feasibility + design gates, not a safety failure)
Two design gates in the tool itself, plus a feasibility constraint, make a meaningful run impossible from this phase:
1. **Disabled-root refusal (by design):** `_resolve_root` raises `DryRunError("Root key 'syn-work' is disabled;
   refusing to scan.")` when `enabled=false` (`:132-133`). Our `syn-work` draft/scratch config is `enabled=false`
   (correct — activation is not authorized). Passing `--root-key syn-work` → controlled refusal (exit 3).
2. **Unmounted-root refusal (by design):** `_resolve_root` raises `"...does not exist or is unmounted; refusing to
   scan."` when the root path is not a local dir (`:143`). The NAS path `/volume1/homes/bfetting/Work` is **not
   locally mounted** on the Mac.
3. **No NAS repo checkout:** the tool imports `hb_assistant.*`; there is no repo/venv on the NAS to run it there as
   svc against the native path.

Running it "for real" would require **enabling** the root and/or mounting/activating — both explicitly out of scope
for N5B. The safe, faithful action is to **defer** the first-indexing dry-run to N5C (or a later bounded, authorized
phase that runs it on the NAS against an intentionally-enabled scratch config, isolated from production DB/vault).

## What this does NOT block
The availability objective is already met by the stat-only proofs (`03` svc NAS stat; `06` repo probe). The dry-run is
a deeper "what-would-index" preview, not a reachability proof.
