# N2C-V · 04 — bfetting Admin Control Path (FINAL)

## Why this gate exists
Before demoting the runtime service account, an independent **human admin** control path had to be
proven, so that least-privilege on `personal-assistant-svc` never becomes a lockout.

## Operator machine proof (captured before demotion)
- Identity: `uid=1026(bfetting) gid=100(users) groups=100(users),101(administrators)`
  — `bfetting` is in `administrators`.
- **SSH** to the NAS on port `10021` as `bfetting`: **succeeds**.
- **sudo** as `bfetting`: **succeeds** (can run privileged ops incl. `synofirewall`,
  `sudo -u personal-assistant-svc …`).

## Sequencing invariant honored
`bfetting` SSH + sudo were verified **before** `personal-assistant-svc` was removed from
`administrators`. The demotion therefore did not remove the only admin access.

## Ongoing operational model
- **Admin / privileged ops** → `bfetting` (SSH + sudo).
- **Runtime service actions as svc** → `bfetting` then `sudo -u personal-assistant-svc <cmd>`
  (svc has no direct login; see `05`).

**Gate: PASS.**
