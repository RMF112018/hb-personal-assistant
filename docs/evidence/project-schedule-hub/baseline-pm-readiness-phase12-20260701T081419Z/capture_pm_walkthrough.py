#!/usr/bin/env python3
"""Capture Phase 12 pre/post-fix PM walkthrough screenshots."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

STAMP = "20260701T081419Z"
EVIDENCE = Path(__file__).resolve().parent
SHOT_DIR = EVIDENCE / "screenshots" / (sys.argv[1] if len(sys.argv) > 1 else "pre-fix")
SHOT_DIR.mkdir(parents=True, exist_ok=True)

AS_OF = "2026-07-01"
BASE = "http://127.0.0.1:5173"
DRIVER_URL = (
    f"{BASE}/projects/tropical/schedule/driver-detail"
    f"?activity_id=FAB%2FDEL-10&comparison_basis=current_contract_baseline&as_of={AS_OF}"
)
WORKBENCH_URL = (
    f"{BASE}/projects/tropical/schedule/workbench"
    f"?comparison_basis=current_contract_baseline&as_of={AS_OF}"
)

SCRIPT = f"""
const {{ chromium }} = require('playwright');
(async () => {{
  const browser = await chromium.launch();
  const page = await browser.newPage({{ viewport: {{ width: 1440, height: 900 }} }});
  await page.addInitScript(() => localStorage.setItem('hb-ui-role', 'operator'));
  const shots = {json.dumps(str(SHOT_DIR))};

  await page.goto('{BASE}/projects/tropical/schedule?as_of={AS_OF}', {{ waitUntil: 'domcontentloaded' }});
  await page.waitForSelector('text=Baseline Anchors', {{ timeout: 60000 }});
  await page.waitForTimeout(1500);
  await page.screenshot({{ path: shots + '/01-schedule-hub.png', fullPage: true }});

  const ccb = page.getByRole('button', {{ name: 'Current Contract Baseline', exact: true }});
  if (await ccb.count()) await ccb.first().click();
  await page.waitForTimeout(1500);
  await page.screenshot({{ path: shots + '/02-controls-named-baseline.png', fullPage: true }});

  await page.goto('{WORKBENCH_URL}', {{ waitUntil: 'domcontentloaded' }});
  await page.waitForSelector('text=Schedule Workbench', {{ timeout: 60000 }});
  await page.waitForSelector('text=Named baseline preview', {{ timeout: 60000 }});
  await page.waitForTimeout(1500);
  await page.screenshot({{ path: shots + '/03-workbench-named-baseline.png', fullPage: true }});

  await page.goto('{BASE}/projects/tropical/schedule/workbench?comparison_basis=secondary_progress_update_baseline&as_of={AS_OF}', {{ waitUntil: 'domcontentloaded' }});
  await page.waitForTimeout(1500);
  await page.screenshot({{ path: shots + '/06-missing-baseline-controls.png', fullPage: true }});

  await page.goto('{DRIVER_URL}', {{ waitUntil: 'domcontentloaded' }});
  await page.waitForSelector('text=Side-by-Side Movement', {{ timeout: 60000 }});
  await page.waitForTimeout(1500);
  await page.screenshot({{ path: shots + '/04-driver-detail-slash-activity.png', fullPage: true }});

  await page.goto('{WORKBENCH_URL}', {{ waitUntil: 'domcontentloaded' }});
  await page.waitForURL('**/schedule/workbench**', {{ timeout: 30000 }});
  await page.waitForTimeout(1500);
  await page.screenshot({{ path: shots + '/05-back-to-workbench.png', fullPage: true }});

  console.log(JSON.stringify({{
    driverUrl: page.url(),
    workbenchUrl: page.url(),
    driverTitle: await page.title(),
  }}));
  await browser.close();
}})();
"""

tmpdir = Path("/tmp/hb-phase12-playwright")
tmpdir.mkdir(exist_ok=True)
js_path = tmpdir / "capture.js"
js_path.write_text(SCRIPT)
subprocess.run(["npm", "init", "-y"], cwd=tmpdir, capture_output=True)
subprocess.run(["npm", "install", "playwright@1.49.1"], cwd=tmpdir, capture_output=True)
subprocess.run(["npx", "playwright", "install", "chromium"], cwd=tmpdir, capture_output=True)
result = subprocess.run(["node", str(js_path)], cwd=tmpdir, capture_output=True, text=True)
print(result.stdout)
if result.stderr:
    print(result.stderr, file=sys.stderr)
sys.exit(result.returncode)
