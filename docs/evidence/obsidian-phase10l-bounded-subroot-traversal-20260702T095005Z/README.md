# Phase 10L — Bounded Subroot Traversal + Corrected Availability Finding

Read-only pass. **No vault write, DB apply, source hydration, source/queue/runtime mutation, push, or
PR.** All safe evidence is count-only; row/path detail is git-ignored under `local-sensitive/`.

## Corrected conclusion
The earlier "source availability blocker" framing was too strong. Root-level EINTR does not prove all
descendants are unavailable: `lstat` (no hydration) confirms a named construction descendant exists under
the dormant root. The indexers/probe now support bounded `--include-subroot` traversal that starts at an
explicit, contained, symlink-safe descendant — bypassing the failing root scandir — while project
identity stays bound to `--source-root`. See `05-findings/findings-safe.md`. The prior evidence folder
`obsidian-phase10l-tropical-source-availability-*/05-findings/findings-safe.md` carries an appended dated
CORRECTION block (original text preserved).

## Live status
On this machine the cited construction subroot exists but is still dormant for headless `scandir`, so the
bounded dry-run selects 0 candidates pending "Make Available Offline" on the specific subfolder. The
feature itself is proven by the unit tests in `04-tests/`.
