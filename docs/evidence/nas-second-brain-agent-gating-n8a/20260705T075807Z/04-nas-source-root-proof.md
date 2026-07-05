# 04 — NAS Source-Root Proof (Reference to N8 PASS)

**N8A performs no new source-root creation.** The bounded NAS source-root proof already ran live and **PASS** in N8.

## Reference

- **N8 live proof:** `../../nas-second-brain-agent-gating-n8/live-20260704/04-live-nas-source-root-proof.md` — **PASS**. A bounded, isolated NAS test source root (`source_root_key=nas_test`, 3 synthetic files `note-a.txt`, `note-b.txt`, `shared/x.txt`) under `/volume2/personal-assistant/…`, plus a second root (`nas_test2` / `test-source-root-2`, added in proof 07 for cross-root non-collision).
- Identity is root-scoped: `source_id_for("external_file", source_root_key=…, rel_path=…)` (`obsidian_mcp/source_index_repository.py:35`).

## N8A confirmation (read-only, this session)

**Confirmed at rest:** the `nas_test` lineage is intact — its bounded card (`Source Notes/Shared/note-a.txt__482f41ec8a37.md`) and the proof backups are present under `/volume2/personal-assistant/…` (`../live-20260705T075807Z/01-live-state-reconciliation.md`). The definitive `sources` row-count per root (`nas_test` / `nas_test2`) is a pending optional root read-only pass (DB is `0600` svc-owned). No new root, no new ingestion.

## Verdict

**PASS by reference** (N8 live 04); NAS-local lineage confirmed at rest. No new root.
