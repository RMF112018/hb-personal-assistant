# No Raw Leak Scan Template

Run the repo-true scanner after evidence is generated. Generation-time examples indicate either a dedicated `email-calendar raw no-raw-leak-scan` command or helper-level scanner usage may exist.

Preferred command if still present:

```bash
.venv/bin/hb-assistant email-calendar raw no-raw-leak-scan   --path docs/evidence/phase-10-daily-brief-effectiveness-ranking-policy-telemetry   --json   2>&1 | tee "$ROLL/no-raw-leak-scan.json"
```

If command shape differs, use the repo-true scanner. Findings may include category codes only, never matched strings.

Required planted categories in tests:

- `url`
- `email`
- `join_link`
- `jwt_like`
- `access_token`
- `bearer`
- `private_key`
- local absolute path category if repo has one
