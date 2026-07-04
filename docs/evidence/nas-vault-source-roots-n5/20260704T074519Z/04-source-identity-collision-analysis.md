# 04 — Source Identity / Duplicate-Collision Analysis

## Identity model (confirmed in current code)
`source_id = sha256("{source_kind}|file|{rel_path}")[:32]` (`source_index_repository.py:38`), where
`rel_path = abs_path.relative_to(root.path)`. DB unique index `(source_kind, rel_path)`
(`source_intelligence_tables.py:110`). **Root key and absolute path are NOT part of identity.** `abs_path_hash` is
stored but never read in any WHERE/lookup.

## Consequence for migration
| Scenario | rel_path | source_id | Outcome | Risk |
|---|---|---|---|---|
| Repoint root to NAS, **same `source_root_key` + same tree** | unchanged | unchanged | no dup rows, no orphaned cards, stale-but-unused `abs_path_hash` | **LOW** |
| Add NAS as a **new root alongside** the Mac root (both active) | same | same | `(kind,rel_path)` collision → upsert silently rewrites `source_root_key` on the shared row (cross-root aliasing) | **HIGH** |
| Reshuffle internal layout on NAS | changed | changed (new id) | duplicate source rows; old rows `deleted=1`, their generated notes/summaries go stale/orphaned | **HIGH** |

## Load-bearing defect
`source_index_repository.py:38` + unique index omit `source_root_key`. Latent cross-root collision. **Not triggered**
by the recommended same-key/same-tree repoint. **Must be fixed before any multi-root NAS activation** (add
`source_root_key` to the identity key + unique index, migration-guarded) — carried into the hardening plan (10) and N8.

## Root-remap
No path-rebase/remap tool exists (`register_source_roots` only records active keys + deactivates removed ones).
Because identity is rel_path-based, none is needed: repoint = edit config `external_sources[*].path` (system A) and
`local_sync_path` (system B); startup re-registration reconciles the DB. No DB rewrite/migration table required.

## Frontmatter / wikilinks
Notes contain only relative `source_path` + logical `source_root_key` + hashes — relocating the vault/roots does not
break note content or links.

## syn-work repoint — CONFIRMED same-tree (LOW)
Operator-confirmed NAS-native path `/volume1/homes/bfetting/Work` has top-level `NAS - HB` + `Altman`, matching the
two top-level segments of the 126 `syn-work` rel_paths (101 + 25) → identical rel_path tree. Repointing
`external_sources[source_root_key='syn-work'].path` to it keeps `source_root_key` + rel_paths unchanged ⇒ `source_id`
unchanged ⇒ no duplicates/orphans. svc can read it read-only (traverse chain all others-x). No copy required.

## Risk rating (recommended approach): **LOW**
Provided: (1) same `source_root_key`, (2) identical rel_path tree (vault + syn-work both verified), (3) **never**
Mac + NAS roots active together, (4) fix the identity defect before multi-root activation (N8). Anti-patterns raise it to HIGH.
