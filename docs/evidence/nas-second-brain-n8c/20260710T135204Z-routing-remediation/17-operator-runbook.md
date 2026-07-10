# Operator runbook — freshness-fix deploy + manifest r3

**Land commit:** `f565b19b1525fbeef75077c53be2b3bb0520c274`

R2 manifest promote on NAS **succeeded** (`manifest_id=ffe6c90d60b2818122b7a2a7`, version 4) but the **container still runs `f53cba1c`** — pre-promote showed `family_changed: 145` and identical checksum `5ac5677779777f6fa7e62b05` (no semantic change). Re-promote on old code cannot clear `surface_stale`.

## 1. Build image (Mac)

```bash
cd /Users/bobbyfetting/hb-personal-assistant
git checkout f565b19b1525fbeef75077c53be2b3bb0520c274
docker build --platform linux/amd64 -f deploy/nas/Dockerfile -t hb-personal-assistant:nas .
docker save hb-personal-assistant:nas | gzip > /tmp/hb-nas-f565b19b.tar.gz
shasum -a 256 /tmp/hb-nas-f565b19b.tar.gz
```

## 2. Transfer (Synology: use `ssh cat`, not `scp`)

```bash
EVID=/Users/bobbyfetting/hb-personal-assistant/docs/evidence/nas-second-brain-n8c/20260710T135204Z-routing-remediation

ssh hb-nas 'cat > /tmp/hb-nas-f565b19b.tar.gz' < /tmp/hb-nas-f565b19b.tar.gz
ssh hb-nas 'cat > /tmp/hb-deploy-freshness-fix.sh' < "$EVID/17-deploy-freshness-fix.sh"
ssh hb-nas 'cat > /tmp/hb-manifest-refresh.sh' < "$EVID/14-manifest-refresh.sh"
ssh hb-nas 'cat > /tmp/hb-manifest-verify-only.sh' < "$EVID/15-manifest-verify-only.sh"
```

## 3. Deploy fix

```bash
ssh -t hb-nas 'sudo sh /tmp/hb-deploy-freshness-fix.sh' | tee ~/deploy-freshness-fix.txt
```

Step 7 should print `stale False family_changed 0 class_changed 0` (may still be stale until manifest r3 if profile not stamped).

## 4. Manifest refresh r3

```bash
ssh -t hb-nas 'sudo sh /tmp/hb-manifest-refresh.sh' | tee ~/manifest-refresh-r3.txt
```

Expect new checksum (not `5ac56777…`) and step 4 + 5 pass.

## 5. Verify-only (optional double-check)

```bash
ssh -t hb-nas 'sudo sh /tmp/hb-manifest-verify-only.sh' | tee ~/manifest-verify-r3.txt
```

Pass criteria: step **4b** `stale false`; step **5** `document_session` not `surface_stale`.