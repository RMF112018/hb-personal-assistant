# Canonical CLI Contract

## Root

```bash
hb-assistant --version
hb-assistant --help
```

## Auth

```bash
hb-assistant auth login --json
hb-assistant auth status --json
hb-assistant auth logout --json
hb-assistant auth clear-cache --json
```

## Diagnostics

```bash
hb-assistant diagnostics env --json
hb-assistant diagnostics auth --json
hb-assistant diagnostics graph --safe --json
hb-assistant diagnostics proof delegated-graph --json
hb-assistant diagnostics automation --json
hb-assistant diagnostics scan-sensitive --repo . --json
```

## Files

```bash
hb-assistant files sample --json
hb-assistant files ingest --dry-run --json
```

## Search

```bash
hb-assistant search query "project status" --json
```

## Run

```bash
hb-assistant run morning --dry-run --json
hb-assistant run morning --json
```

## Automation

```bash
hb-assistant automation install-launchd --dry-run --json
hb-assistant automation install-launchd --json
hb-assistant automation uninstall-launchd --dry-run --json
hb-assistant automation kickstart --json
```
