# 08 — Live deploy validation (BLOCKED)

## Gate decision

| Item | Status |
|------|--------|
| Pre-deploy snapshot | DONE (`08-predeploy-runtime-snapshot.md`) |
| Image build (linux/amd64) | DONE (`hb-personal-assistant:nas` e33083c0…) |
| Image staged on NAS `/tmp` | DONE (sha256 match Mac↔NAS) |
| Container recreate / image load | **BLOCKED** — host sudo password required |
| Live surface matches branch (87 tools, structure ON) | **NO** (still v1.3.0 / 78 tools) |
| 13-case matrix re-run on new deploy | **NOT RUN** (runtime unchanged) |
| Push/PR | **NOT AUTHORIZED** |

## Worktree

| Field | Value |
|-------|-------|
| Branch | `ops/source-index-client-performance-hardening-20260709` |
| HEAD | `2a61b4fb01d785d0832c60a0247243a6771b4e77` |
| origin/main | `2e98a03d56f54b25fef86bd3b4c19a89185988cc` |
| Status | `?? docs/evidence/nas-source-index-client-performance-hardening/20260709T000000Z/08-build-artifact-meta.txt
?? docs/evidence/nas-source-index-client-performance-hardening/20260709T000000Z/08-live-deploy-validation.json
?? docs/evidence/nas-source-index-client-performance-hardening/20260709T000000Z/08-live-deploy-validation.md
?? docs/evidence/nas-source-index-client-performance-hardening/20260709T000000Z/08-predeploy-runtime-snapshot.json
?? docs/evidence/nas-source-index-client-performance-hardening/20260709T000000Z/08-predeploy-runtime-snapshot.md` |

```
2a61b4fb (HEAD -> ops/source-index-client-performance-hardening-20260709) docs(evidence): live authenticated connected-client matrix results
efc95d2c docs(evidence): post-rebase validation onto origin/main
68d77b08 docs(evidence): 05-TIP points to git rev-parse HEAD as authority
ad7821f2 docs(evidence): point 05-TIP.txt at its own commit
fd43c3cd docs(evidence): add 05-TIP.txt with branch tip hash pointer
69c49cc8 docs(evidence): authoritative closeout HEAD inventory and report
9f895892 docs(evidence): final HEAD stamp for closeout tip
4ad2127e docs(evidence): fix closeout HEAD inventory text and final report
```

## Deployment method attempted

Repo-truth path (`deploy/nas/BUILD.md` + prior N8C deploy closeout):

1. Mac: `docker buildx build --platform linux/amd64 -f deploy/nas/Dockerfile -t hb-personal-assistant:nas --load .`
2. Mac: `docker save | gzip` → ship `ssh hb-nas "cat > /tmp/….tar.gz"`
3. NAS: `sudo docker load` + `sudo /volume2/personal-assistant/bin/hb-mcp-runner stop|start`

Step 3 failed: `sudo: a password is required` (batch SSH; NOPASSWD not valid for volume2 runner).

### Build / staging (no secrets)

```
tag=hb-nas-source-index-2a61b4fb01d7
head=2a61b4fb01d785d0832c60a0247243a6771b4e77
image_id=sha256:e33083c0124512562dcd70f6b76b119c60c04489fbe4805f88dce2b60cbefc76
tarball=/tmp/hb-nas-source-index-2a61b4fb01d7.tar.gz
675a637aeec81a4c594294102bb075c313df835075fc817d5f56fc2a953520f4  /tmp/hb-nas-source-index-2a61b4fb01d7.tar.gz
nas_path=/tmp/hb-nas-source-index-2a61b4fb01d7.tar.gz
operator_script=/tmp/hb-deploy-source-index.sh
```

Operator script on NAS: `/tmp/hb-deploy-source-index.sh`

## Prior runtime snapshot

See `08-predeploy-runtime-snapshot.md`. Pre-deploy live: health 200; tools/list assistant **78**; structure/health/plan/map tools absent; `assistant_output_*` = 0; runtime_commit `v1.3.0`; `/mcp/` 307→`http://127.0.0.1:8765/mcp`.

## Post-attempt live surface (unchanged)

| Probe | Result |
|-------|--------|
| `/health` | 200 |
| `/mcp` unauthenticated | 401 |
| `/mcp` authed initialize | 200 serverInfo={'name': 'hb-nas-mcp', 'version': '1.28.1'} |
| tools/list total | 163 |
| assistant tools | 78 |
| required new tools | {'assistant_source_index_health': False, 'assistant_source_query_plan': False, 'assistant_source_project_map': False, 'assistant_source_folder_map': False} |
| assistant_output_* | 0 |
| `/mcp/` trailing slash | {'http': 307, 'location': 'http://127.0.0.1:8765/mcp'} |

## 13-case matrix

Not re-executed (deploy not applied). Pre-deploy matrix: `07-live-connected-client-results.md` (**8/13**).

## `/mcp/` redirect defect

- `POST /mcp/` → **307** `Location: http://127.0.0.1:8765/mcp` (remote-broken)
- Workaround: use **`/mcp`** without trailing slash (works)
- Not fixed in this session; separate low-risk proxy/app defect
- Does not uniquely block source-index feature if clients omit trailing slash

## Kill-switch

Not retested on host (would need restart). Local post-rebase proof: `06-post-rebase-inventory-and-matrix.json`.

## Cleanup ledger

| Artifact | Disposition |
|----------|-------------|
| Live temp outputs from run 07 | Already archived in case 9 of 07 |
| New temp outputs this attempt | None created |
| NAS `/tmp` image tarball | Staged for operator deploy; remove after load |
| Origin bearer token | Not written to evidence |

## Operator resume (one interactive sudo)

```sh
ssh hb-nas
sh /tmp/hb-deploy-source-index.sh   # enter sudo password
```

Then re-run authenticated live matrix; expect assistant tools **87**, structure default-ON, all required tools + 10 aliases.

Optional sudoers fix (operator review only):

```
bfetting ALL=(root) NOPASSWD: /volume2/personal-assistant/bin/hb-mcp-runner
```

## Defect classification

| Defect | Class |
|--------|-------|
| Cannot docker load / recreate MCP | **deployment host privilege / sudoers path drift** |
| Live still 78 tools | **stale runtime** (blocked by above) |
| `/mcp/` → 127.0.0.1 | **proxy/app redirect** (separate) |

## Recommendation

Operator completes staged deploy script → re-run live matrix → only then push/PR or explicitly authorize PR with pending live.

**No push, no PR from this agent.**

---

## Postscript — operator deploy completed; matrix re-run

After this note was first written (deploy **BLOCKED** on sudo), the operator ran `/tmp/hb-deploy-source-index.sh` on the NAS. Post-deploy live matrix evidence:

- `09-postdeploy-live-matrix.md` / `.json`
- Score: **13/13 PASS**
- Surface: assistant exposed **87**, structure default-ON, required health/plan/map tools present, **10** `assistant_output_*` aliases listed
- Residual: `assistant_output_stage` listed but broker `tool_not_registered` — use `pa_output_*` for writes
- Push/PR: still requires explicit operator authorize (no auto-push from agent)

