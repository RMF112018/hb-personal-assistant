"""Deterministic stub of the model-engine runtime (no statsforecast) for adapter/boundary tests.

Honors the same JSON contract as model_engine_runtime/runner.py so the subprocess boundary can be
exercised under the 3.14 interpreter. Forecast is a naive placeholder: etc = last_value * horizon.
"""

import json
import sys


def main() -> int:
    payload = json.loads(sys.stdin.read())
    results = {}
    for req in sorted(payload.get("requests", []), key=lambda r: str(r.get("id"))):
        series = [float(x) for x in (req.get("series") or [])]
        h = int(req.get("horizon") or 0)
        etc = (series[-1] * h) if series and h > 0 else 0.0
        results[str(req.get("id"))] = {
            "etc": etc,
            "per_model_etc": {"stub_naive": etc},
            "model_set": ["stub_naive"],
            "fallback_used": False,
            "applicable": bool(series and h > 0),
        }
    json.dump({"backend": "stub_runtime", "results": results}, sys.stdout, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
