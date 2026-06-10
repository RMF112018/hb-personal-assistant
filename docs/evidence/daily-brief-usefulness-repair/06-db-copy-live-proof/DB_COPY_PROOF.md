# Priority 6 — DB-Copy Live Proof (Prompt 06)

Production DB stays read-only. All apply-mode writes hit a `.backup` copy under `/tmp`; all browser /
status / Obsidian outputs are written under `/tmp`. Raw local content (real meeting subjects in the
browser/Obsidian brief) stays in `/tmp` and is referenced by path only — never copied into repo
evidence. Repo evidence here is counts / hashes / redacted summaries only.

## Procedure (matches `validation/VALIDATION_COMMANDS.md`)

1. `sqlite3 "$PROD_DB" ".backup '$AUDIT_DB'"` (PROD_DB = `PathPolicy().get_db_path()`, the V45 audit DB).
2. `PRAGMA integrity_check` → `ok`; `PRAGMA quick_check` → `ok` (see `integrity_check.txt` / `quick_check.txt`).
3. `shasum -a 256 "$PROD_DB"` before.
4. `hb-assistant second-brain daily-run run --apply --raw --write-obsidian --confirm-vault-write
   --as-of 2026-06-10T05:00:00-04:00 --vault-brief-dir/--browser-output-dir/--status-dir <under /tmp>
   --db "$AUDIT_DB" --json`.
5. `shasum -a 256 "$PROD_DB"` after.

## Production DB unchanged ✓

```
before: f93b78081dfbbd7d40ebbfc9254227eab7d306bb08d73e8b92d76e7b33ae4759
after:  f93b78081dfbbd7d40ebbfc9254227eab7d306bb08d73e8b92d76e7b33ae4759
```
Identical (see `prod-before.sha256` / `prod-after.sha256`).

## Result — deterministic substrate repaired (no false success)

| Audit metric | Before (audit) | After (DB-copy run) |
|---|---:|---:|
| daily_brief_candidate_count (target date) | 0 | **18** (calendar 8, procore 10) |
| candidate_source_ref_coverage | 0.0 | **1.0** (18/18) |
| executive source-ref coverage | 0.0 | **1.0** |
| calendar_project_resolution_rate | 0.0 | **1.0** (5 project-like, 0 unresolved) |
| procore aggregate sludge selected (executive) | 3,592 dominating | **0** |
| deterministic_section_count | 0 | **2** (calendar + procore) |
| guard-column sum on persisted candidates | — | **0** |

Persisted candidate distribution (safe project keys / counts only):

```
calendar | tropical            | 3
calendar | the-wellington      | 1
calendar | alton-hilltop-pbg   | 1
calendar | __internal_training__ | 1
calendar | __internal_time_off__ | 1
calendar | __internal_company__  | 1
procore  | tropical            | 10
```

Project meetings resolve to real keys; internal events are categorized separately; nothing is stuck
as `__unassigned__`; Procore executive rows are ranked (no aggregate sludge).

## Status / gate

- `status = partial`, `brief_freshness = fresh`.
- **Usefulness gate `verdict = useful`, `passed = true`, `failed_reasons = []`** — the deterministic
  layer IS operator-useful.
- The `partial` downgrade is the **local-model synthesis fail-closing** on empty/low-quality output
  (`synthesis_degraded`, reason `empty_synthesis_low_quality`) — the deterministic source-linked brief
  is rendered as the fallback and the run is NOT counted as a fresh success. This is correct
  fail-closed behavior, not a false success.
- Because `status != success`, `daily-brief-latest.html` was **not** overwritten and the
  last-successful brief is preserved (outputs contain `browser_dated_path` + `browser_attempted_path`,
  no `browser_latest_path`).
- Egress scan: clean (`matched_labels: []`).

## Safety

- Production DB hash unchanged (above).
- Guard columns all zero on persisted candidates.
- Outputs only under `/tmp` (redacted relative paths in `latest-status.safe.json`).
- Forbidden-string scan over `docs/evidence/daily-brief-usefulness-repair`: **clean**.

Artifacts: `integrity_check.txt`, `quick_check.txt`, `prod-before.sha256`, `prod-after.sha256`,
`latest-status.safe.json` (sanitized status — usefulness_gate + summary + redacted outputs).
Raw `/tmp` artifacts (browser HTML, Obsidian note) referenced by path only in the final handoff.
