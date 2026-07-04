# 04 — Bounded NAS Test Source Root — RUNBOOK (PENDING LIVE EXECUTION WITH BOBBY)

Status: **HOLD** — requires live NAS access + Bobby's per-step approval. Not executed this session.

## Plan
1. On the NAS, create a **bounded** dedicated test root, e.g. `/volume2/personal-assistant/test-source-root/`,
   containing **2–3 synthetic, non-sensitive** files (e.g. `note-a.txt`, `note-b.txt`, `shared/x.txt`).
2. Configure exactly one `ExternalSourceRoot` in the **runtime** config (uncommitted, under
   `local-sensitive/`, sha-recorded), with a **distinct** `source_root_key` (e.g. `nas_test`):
   ```yaml
   external_sources:
     - source_root_key: nas_test
       path: /volume2/personal-assistant/test-source-root
       enabled: true
   ```
3. Prove: the root resolves, is enabled, is **isolated** from Home/Work/Shared (distinct key + path),
   and the obsidian_vault points at a **NAS-local** path (never the Mac vault).

## Acceptance
- Root registered (`register_source_roots`) with `source_root_key=nas_test`.
- Config sha recorded to `local-sensitive/`; no secrets in the committed evidence.
- Vault path is under `/volume2/personal-assistant/…` (assert ≠ Mac vault — stop condition).
