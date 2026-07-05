# 06 — Bounded Obsidian Write Proof (Reference to N8 PASS) + Config-Drift Cross-Link

**N8A generates no new card.** The bounded one-card write already ran live and **PASS** in N8.

## Reference

- **N8 live proof:** `../../nas-second-brain-agent-gating-n8/live-20260704/06-live-bounded-obsidian-card-proof.md` — **PASS**.
  - Real code path `source_notes.generate_source_card(overwrite=False)` for `nas_test/note-a.txt`.
  - One card `Source Notes/Shared/note-a.txt__482f41ec8a37.md` into the NAS vault `/volume2/personal-assistant/vault/obsidian`; `generated_notes` **195 → 196 (+1)**; everything else unchanged. Atomic temp + `os.replace`, SHA optimistic-concurrency, vault-root containment; filename carries `source_id[:12]`.
  - Wrong-vault stop-condition guarded (must be the NAS vault, never the Mac vault).

## Config-drift cross-link (the failure this proof surfaced)

Proof 06 initially hit a `DbStorageGuardError` on the mutation-audit write because the **live NAS configs still set `application_support_root` at `/volume1`** (N8 finding `06a`). Proof 06 worked around it with a container-only `/volume2` `HB_PA_CONFIG`; **no live config was fixed** in N8.

**N8A remediates this drift live** (operator-approved): `../live-20260705T075807Z/02-config-drift-remediation.md` edits both live configs to `/volume2` (preserving the `_vault_disabled` sentinel — no new vault-write enablement). This closes the storage-guard failure at its root.

## N8A confirmation (read-only, this session)

**Confirmed at rest:** the one N8 card `Source Notes/Shared/note-a.txt__482f41ec8a37.md` is present in the NAS vault, unchanged (`../live-20260705T075807Z/01-live-state-reconciliation.md` §3). The `/volume1` drift that caused Proof 06's stop-condition is **already resolved** on the live NAS (`../live-20260705T075807Z/02-config-drift-remediation.md`) — no edit needed. `generated_notes` count unchanged (DB read-only count is a pending optional root pass; no new card was generated).

## Verdict

**PASS by reference** (N8 live 06); card confirmed at rest; the root-cause `/volume1` drift is confirmed resolved. No new card.
