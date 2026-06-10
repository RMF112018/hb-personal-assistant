# Last-success preservation proof

The last-successful pointer is updated ONLY on a fresh success. A degraded/partial/failed run never overwrites it, so the operator always retains a pointer to the last good brief.

- run 1 (deterministic) result: **success** · freshness: fresh · pointer written: True
- run 2 (synthesis requested) result: **degraded** · synthesis_degraded: True
- pointer unchanged across the degraded run: **True**
