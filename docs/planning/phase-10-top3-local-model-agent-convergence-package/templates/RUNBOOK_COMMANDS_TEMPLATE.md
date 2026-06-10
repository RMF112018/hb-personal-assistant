# Runbook Command Template

Replace DB paths with the local DB-copy paths discovered by the agent.

## Daily-run dry-run

```bash
hb-assistant second-brain daily-run run --dry-run --json
```

## Daily-run apply on DB copy

```bash
hb-assistant second-brain daily-run run \
  --apply \
  --db /tmp/hb-pa-phase10-top3-copy.sqlite \
  --max-persist-per-stage 10 \
  --max-total-persist 30 \
  --json
```

## Disable Model Enriched Intelligence

```bash
hb-assistant second-brain daily-run run \
  --dry-run \
  --no-model-enriched-intelligence \
  --json
```

## Email raw enrichment readiness

```bash
hb-assistant second-brain follow-up-watch enrich-readiness \
  --db /tmp/hb-pa-phase10-top3-copy.sqlite \
  --json
```

## Scheduler install preview

```bash
hb-assistant second-brain daily-run scheduler install --dry-run --json
```

## Scheduler status

```bash
hb-assistant second-brain daily-run scheduler status --json
```
