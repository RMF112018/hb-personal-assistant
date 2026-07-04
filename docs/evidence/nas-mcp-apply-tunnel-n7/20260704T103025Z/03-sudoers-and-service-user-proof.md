# 03 — Sudoers and service-user proof

## Service-user SSH (Mac)

```
personal-assistant-svc@hb-nas: Permission denied (publickey,password)
```

**Result:** direct service-user SSH remains **denied**.

## Sudoers

Target content:

```text
bfetting ALL=(root) NOPASSWD: /volume1/personal-assistant/bin/hb-mcp-runner
```

Initial install wrote **0-byte** file (tee/sudo wrapper bug). Corrected before closeout:

```text
76 /etc/sudoers.d/hb-pa-mcp
(root) NOPASSWD: /volume1/personal-assistant/bin/hb-mcp-runner
```

No broad `docker`, `sh`, `bash`, or `ALL` grant observed in `sudo -l`.

Note: `visudo` not available on NAS; validated via file content + `sudo -l`.
