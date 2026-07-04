# 10 — Git status

| Item | Value |
|---|---|
| Branch | `feat/nas-sqlite-hardening-pr-a` |
| **Code commit (validated on NAS)** | `e862cc11` |
| Code SHA (full) | `e862cc119290b441a336a49ab43874ce59aaac02` |
| Code message | `ops(nas): add viewer lifecycle scripts and runbooks` |
| **Evidence commit** | `c81e3084` |
| Evidence SHA (full) | `c81e3084a2424e8f3438b8eab15ea2587266010d` |
| Evidence message | `docs(nas): add PR C viewer lifecycle validation evidence` |
| Evidence metadata patch | `989cbf82` — `docs(nas): clarify PR C code vs evidence commit SHAs` |
| Parent chain | `989cbf82` → `c81e3084` → `e862cc11` → `13f84c2e` → … |
| Push | **Not authorized** |

Excluded from evidence commit: passwords, `local-sensitive/`, raw DB/WAL/SHM, `__MACOSX/`, `._*`.

Untracked (not in either commit): `deploy/nas/scripts/pr-c-viewer-lifecycle-run.sh` — operator helper used for this validation run; decision deferred (see closeout follow-ups).
