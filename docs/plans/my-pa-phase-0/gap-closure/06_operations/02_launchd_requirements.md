# launchd Requirements

## Required Plist Fields

- `Label`
- `ProgramArguments`
- `WorkingDirectory`
- `StartCalendarInterval`
- `StandardOutPath`
- `StandardErrorPath`
- `EnvironmentVariables`

## Required ProgramArguments

```text
[
  "<verified hb-assistant executable>",
  "run",
  "morning"
]
```

## Required Readiness Checks

Before real install, diagnostics must confirm:

- executable exists;
- executable is executable;
- working directory exists;
- command `hb-assistant run morning --dry-run --json` succeeds;
- log directories exist/writable;
- Obsidian Daily Notes path exists or can be created safely;
- Application Support path permissions are acceptable.

## Do Not

- Do not derive executable path from Application Support parent.
- Do not install a plist that points to a non-existent binary.
- Do not use stale command grammar.
