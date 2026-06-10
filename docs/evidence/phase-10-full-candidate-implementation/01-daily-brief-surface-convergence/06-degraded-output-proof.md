# Degraded-path proof — pending follow-up section survives synthesis failure

When local-model synthesis is unavailable the daily run renders the degraded brief (`status=partial`, `degraded=True`). The HTML renderer emits the raw-free V45 pending follow-up card **before** the brief body, so it is present on the degraded path too. The section is also produced deterministically with `synthesize_brief=False` (no model at all), proving model synthesis is never required for it to appear.

- pending card present on degraded HTML: **True**
- degraded HTML egress-clean: **True**
- deterministic (no-synthesis) seeded run surfaced the card: **True**
