# 06 — Migration Options

## A — Mirror only, do not activate (RECOMMENDED first step = N5A)
Mirror the vault → NAS; do NOT repoint live config, register roots, or ingest. Lowest risk; proves NAS-local vault
copy; Mac stays authoritative. Collision risk: none (nothing activated).

## B — Mirror + config draft (paired with A in N5A)
Author NAS `config.yml` + `obsidian_mcp_config.json` **drafts** (NAS `vault_root`, same-key source paths) — draft only,
not placed/activated — to unblock N5B/N7. Moderate value, still no runtime.

## C — Mirror + bounded dry-run activation (defer → N5B)
Use `app-support-smoke` scratch root + `obsidian_source_root_availability_probe.py` (stat-only) +
`obsidian_source_first_indexing_dryrun.py` (no DB/card). Report-only path resolution against NAS paths; no production
DB write, no card writes. Higher value; belongs in a dedicated dry-run phase.

## D — Full activation (repoint runtime, register roots, ingest/card-gen)
**REJECTED for N5.** Requires the source-identity fix (§04), auth re-provision, and watcher gating — that is N8.

## Recommendation
**A + B now (as N5A), executed only under separate authorization.** Mirror the small vault, produce non-activated
config drafts. Defer `syn-work` repoint pending the operator path decision (§03/§05). Defer `hb-onedrive` to Graph
re-provision (08). Keep workers/watch/index OFF throughout. Dry-run/activation proofs → N5B; auth → N5C.
