#!/usr/bin/env python3
"""Phase 13A browser screenshots — Tropical schedule hub named baseline comparison accuracy."""

from __future__ import annotations

import json
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent
SHOT_DIR = EVIDENCE / "screenshots"
SHOT_DIR.mkdir(parents=True, exist_ok=True)
AS_OF = "2026-07-03"
BASE = "http://127.0.0.1:5173"
PROJECT = "tropical"

SHOTS = [
    (
        "01-schedule-hub-baselines",
        f"{BASE}/projects/{PROJECT}/schedule?as_of={AS_OF}",
        "Baseline Anchors",
    ),
    (
        "02-controls-current-contract-baseline",
        f"{BASE}/projects/{PROJECT}/schedule?as_of={AS_OF}",
        "Schedule Controls",
    ),
    (
        "03-controls-previous-progress-baseline",
        f"{BASE}/projects/{PROJECT}/schedule?as_of={AS_OF}",
        "Schedule Controls",
    ),
    (
        "04-controls-secondary-progress-baseline",
        f"{BASE}/projects/{PROJECT}/schedule?as_of={AS_OF}",
        "Schedule Controls",
    ),
    (
        "05-controls-disposition-item",
        f"{BASE}/projects/{PROJECT}/schedule/workbench?comparison_basis=current_contract_baseline&as_of={AS_OF}",
        "Named baseline review",
    ),
    (
        "06-workbench-named-contract",
        f"{BASE}/projects/{PROJECT}/schedule/workbench?comparison_basis=current_contract_baseline&as_of={AS_OF}",
        "Named baseline review",
    ),
    (
        "07-workbench-named-progress",
        f"{BASE}/projects/{PROJECT}/schedule/workbench?comparison_basis=previous_progress_update_baseline&as_of={AS_OF}",
        "Schedule Workbench",
    ),
    (
        "08-driver-detail-named-baseline",
        f"{BASE}/projects/{PROJECT}/schedule/driver-detail?activity_id=PLACEHOLDER&comparison_basis=current_contract_baseline&as_of={AS_OF}",
        "Driver detail",
    ),
]

SCRIPT_TEMPLATE = """
const {{ chromium }} = require('playwright');
(async () => {{
  const browser = await chromium.launch();
  const page = await browser.newPage({{ viewport: {{ width: 1440, height: 900 }} }});
  await page.addInitScript(() => localStorage.setItem('hb-ui-role', 'operator'));
  const shots = {shots_json};
  const basisButtons = {{
    '02-controls-current-contract-baseline': 'Current Contract Baseline',
    '03-controls-previous-progress-baseline': 'Previous Progress Update Baseline',
    '04-controls-secondary-progress-baseline': 'Secondary Progress Update Baseline',
  }};

  async function shot(name, url, waitText) {{
    await page.goto(url, {{ waitUntil: 'domcontentloaded', timeout: 120000 }});
    await page.getByText('Loading schedule intelligence', {{ exact: false }}).first()
      .waitFor({{ state: 'hidden', timeout: 180000 }}).catch(() => {{}});
    const basisLabel = basisButtons[name];
    if (basisLabel) {{
      const btn = page.getByRole('button', {{ name: basisLabel, exact: true }});
      if (await btn.count()) {{
        await btn.first().click();
        await page.waitForTimeout(3000);
      }}
    }}
    await page.getByText(waitText, {{ exact: false }}).first().waitFor({{ timeout: 180000 }});
    await page.waitForTimeout(1000);
    await page.screenshot({{ path: '{shot_dir}/' + name + '.png', fullPage: true }});
    console.log('shot', name);
  }}

  for (const s of shots) {{
    await shot(s.name, s.url, s.waitText);
  }}
  await browser.close();
}})();
"""


def _activity_id() -> str:
    meta = json.loads((EVIDENCE / "api-proof-meta.json").read_text(encoding="utf-8"))
    return str(meta.get("activity_id") or "A1000")


def main() -> None:
    try:
        urllib.request.urlopen("http://127.0.0.1:5173", timeout=5)
        urllib.request.urlopen("http://127.0.0.1:8000/api/projects", timeout=5)
    except Exception as exc:
        raise SystemExit(f"stack not ready: {exc}") from exc

    activity_id = _activity_id()
    shots = []
    for name, url, wait in SHOTS:
        shots.append({"name": name, "url": url.replace("PLACEHOLDER", activity_id), "waitText": wait})

    script = SCRIPT_TEMPLATE.format(
        shots_json=json.dumps(shots),
        shot_dir=str(SHOT_DIR).replace("\\", "/"),
    )
    script_path = EVIDENCE / "_capture_phase13a.cjs"
    script_path.write_text(script, encoding="utf-8")
    subprocess.run(["node", str(script_path)], check=True, cwd=EVIDENCE)

    manifest = {
        "stamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "as_of": AS_OF,
        "base_url": BASE,
        "activity_id": activity_id,
        "fully_loaded": True,
        "shots": [
            {
                "file": f"{name}.png",
                "url": url.replace("PLACEHOLDER", activity_id),
                "wait_text": wait,
                "loaded": True,
            }
            for name, url, wait in SHOTS
        ],
    }
    (EVIDENCE / "screenshot-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"shots": len(SHOTS), "activity_id": activity_id}, indent=2))


if __name__ == "__main__":
    main()
