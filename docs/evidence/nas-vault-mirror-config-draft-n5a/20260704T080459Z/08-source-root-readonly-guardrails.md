# 08 — Source-Root Read-Only Guardrails (carry-forward)

N5A mirrors only the vault. The `syn-work` root is **not** copied (it is NAS-native). These guardrails are recorded
in the draft and carried forward to activation phases.

## `syn-work` = `/volume1/homes/bfetting/Work` (NAS-native; repoint, no copy)
- Operator-confirmed NAS-native; top-level `NAS - HB` + `Altman` matches the Mac root's rel_path tree, so the same
  `source_root_key` + same tree keeps `source_id` stable (no duplicate rows / orphan cards).
- **Mode `777` → filesystem does NOT enforce read-only.** The config-level control is the guard: register the root
  `read_only=True` (as the draft does) and run no write-capable workflow against it unless perms or a bind-mount
  control are tightened separately.
- Draft posture: `enabled=false`, `read_only=true` — inert until an authorized activation phase.

## Source-identity defect (gates multi-root activation — N8)
- `source_index_repository.py:38`: `source_id = sha256("{source_kind}|file|{rel_path}")[:32]` — **rel_path only**,
  omits `source_root_key`; `abs_path_hash` is stored but never read; unique index `(source_kind, rel_path)`
  (`source_intelligence_tables.py:110`).
- Safe for the recommended same-key/same-tree repoint. **Unsafe** if two roots ever share a rel_path (silent row
  rewrite). Fix — add `source_root_key` to the identity key + unique index, migration-guarded — is required **before
  any multi-root NAS activation**.

## Anti-patterns to avoid at activation (from N5 §8)
- Do not add NAS as *new* roots alongside the Mac roots (both active) — old Mac roots and new NAS roots must never be
  active as equivalent source roots simultaneously.
- Do not reshuffle the internal vault/root layout (rel_path changes → new `source_id` → duplicates + `deleted=1`
  orphans).

## Text Vault
Fail-closed startup preflight (from N4A file 07) must land before production runtime — refuse silent new-key
generation when encrypted refs exist but key/blob material is absent.
