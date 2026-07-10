# Build and transfer — routing remediation deploy

**Type:** code-only (schema head stays **119**). No live-DB migration in this stack.

## 1. Land the code

Commit and push the R1–R6 remediation stack. Record the full SHA:

```sh
git rev-parse HEAD
```

Update `DEPLOY_SHA` and tarball filename in `06-deploy-script.sh`.

## 2. Build image (Mac or CI)

From a clean checkout at the deploy SHA:

```sh
cd /path/to/hb-personal-assistant
git checkout <DEPLOY_SHA>
docker build -f deploy/nas/Dockerfile -t hb-personal-assistant:nas .
docker image inspect hb-personal-assistant:nas --format '{{.Id}}'
```

If bridge DNS fails on NAS, build on Mac and transfer (preferred). See `deploy/nas/BUILD.md`.

## 3. Export tarball

```sh
SHORT=$(git rev-parse --short HEAD)
docker save hb-personal-assistant:nas | gzip > "hb-nas-${SHORT}.tar.gz"
shasum -a 256 "hb-nas-${SHORT}.tar.gz"
```

Record tarball SHA256 in this bundle's post-build notes.

## 4. Transfer to NAS

```sh
scp "hb-nas-${SHORT}.tar.gz" hb-nas:/tmp/hb-nas-${SHORT}.tar.gz
scp docs/evidence/nas-second-brain-n8c/20260710T135204Z-routing-remediation/06-deploy-script.sh hb-nas:/tmp/hb-deploy-routing-remediation.sh
scp docs/evidence/nas-second-brain-n8c/20260710T135204Z-routing-remediation/09-live-40-prompt-probe.sh hb-nas:/tmp/hb-live-40-prompt-probe.sh
```

## 5. Deploy on NAS

```sh
ssh -t hb-nas 'sudo sh /tmp/hb-deploy-routing-remediation.sh' | tee deploy-transcript.txt
```

## 6. Post-deploy probes

```sh
ssh -t hb-nas 'sudo sh /tmp/hb-live-40-prompt-probe.sh' | tee live-40-prompt-probe.txt
```

Copy transcripts back into this evidence bundle as `11-deploy-transcript.md` and `12-live-probe-results.md`.

## Do not (unless separately authorized)

- Run `source-watch bootstrap --apply`
- Call `pa_tool_manifest_refresh_promote` without operator approval
- Enable `HB_MCP_MANIFEST_AUTO_STAGE_ON_DRIFT` or `HB_MCP_MANIFEST_FIRST_INSTALL_AUTOPROMOTE`