#!/usr/bin/env python3
"""Phase 13D mainline browser smoke — 5 shots, strict loaded gates."""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent
SHOT_DIR = EVIDENCE / "09-browser-smoke"
SHOT_DIR.mkdir(parents=True, exist_ok=True)

AS_OF = "2026-07-03"
BASE = "http://127.0.0.1:5173"
PROJECT = "tropical"
ACTIVITY_ID = "FILTER-OUT-50"
SCHEDULE_URL = f"{BASE}/projects/{PROJECT}/schedule?as_of={AS_OF}"

SCRIPT = """
const {{ chromium }} = require('playwright');
const LOADING = ['Loading schedule intelligence', 'Loading schedule controls', 'Loading schedule workbench',
  'Loading driver detail', 'Loading baseline selections', 'Project workspace could not be loaded'];

async function waitGone(page, text, ms = 180000) {{
  const end = Date.now() + ms;
  while (Date.now() < end) {{
    if ((await page.getByText(text, {{ exact: false }}).count()) === 0) return;
    await page.waitForTimeout(400);
  }}
  throw new Error('timeout waiting for: ' + text);
}}

async function assertNotLoading(page, label) {{
  for (const m of LOADING) {{
    if ((await page.getByText(m, {{ exact: false }}).count()) > 0)
      throw new Error(label + ': still loading ' + m);
  }}
}}

(async () => {{
  const browser = await chromium.launch();
  const page = await browser.newPage({{ viewport: {{ width: 1440, height: 900 }} }});
  page.setDefaultTimeout(120000);
  await page.addInitScript(() => localStorage.setItem('hb-ui-role', 'operator'));
  const shots = {shots_dir};
  const proof = {{ stamp: '{stamp}', as_of: '{as_of}', shots: [] }};
  const record = (file, surface, loaded, extra = {{}}) => proof.shots.push({{ file, surface, loaded, ...extra }});

  // 01 hub
  await page.goto('{schedule_url}', {{ waitUntil: 'domcontentloaded', timeout: 120000 }});
  await waitGone(page, 'Loading schedule intelligence');
  const anchors = page.locator('section.card').filter({{ has: page.getByRole('heading', {{ name: 'Baseline Anchors' }}) }}).first();
  await anchors.waitFor({{ state: 'visible', timeout: 120000 }});
  await waitGone(page, 'Loading baseline selections');
  await waitGone(page, 'Loading schedule controls');
  await assertNotLoading(page, 'hub');
  await page.screenshot({{ path: shots + '/01-schedule-hub-named-baselines.png', fullPage: true }});
  record('01-schedule-hub-named-baselines.png', 'Schedule hub named baseline selector', true);

  // 02 controls contract
  const contractBtn = page.getByRole('button', {{ name: 'Current Contract Baseline', exact: true }}).first();
  await contractBtn.click();
  await page.waitForTimeout(2500);
  await waitGone(page, 'Loading schedule controls');
  const controls = page.locator('section.card').filter({{ has: page.getByRole('heading', {{ name: 'Schedule Controls' }}) }}).first();
  await controls.getByText(/Comparing against Current Contract Baseline/i).first().waitFor({{ timeout: 120000 }});
  await controls.getByText(/moved later/i).first().waitFor({{ timeout: 120000 }});
  await assertNotLoading(page, 'controls');
  await page.screenshot({{ path: shots + '/02-controls-current-contract-baseline.png', fullPage: true }});
  record('02-controls-current-contract-baseline.png', 'Controls current_contract_baseline movement', true);

  // 03 workbench
  await page.goto('{wb_url}', {{ waitUntil: 'domcontentloaded' }});
  await page.getByRole('heading', {{ name: 'Schedule Workbench' }}).waitFor({{ timeout: 120000 }});
  await waitGone(page, 'Loading schedule workbench');
  await page.getByText(/current contract baseline/i).first().waitFor({{ timeout: 120000 }});
  await assertNotLoading(page, 'workbench');
  await page.screenshot({{ path: shots + '/03-workbench-named-baseline.png', fullPage: true }});
  record('03-workbench-named-baseline.png', 'Workbench named comparison basis', true);

  // 04 driver detail + disposition
  await page.goto('{driver_url}', {{ waitUntil: 'domcontentloaded' }});
  await waitGone(page, 'Loading driver detail');
  await page.getByText('Side-by-Side Movement', {{ exact: true }}).waitFor({{ timeout: 120000 }});
  await page.getByRole('heading', {{ name: 'Review Disposition' }}).waitFor({{ timeout: 120000 }});
  const disp = page.locator('section').filter({{ has: page.getByRole('heading', {{ name: 'Review Disposition' }}) }}).first();
  const dispText = await disp.textContent();
  if (/psri-|psnbri-/i.test(dispText || '')) throw new Error('raw review id in disposition card');
  await assertNotLoading(page, 'driver');
  await page.screenshot({{ path: shots + '/04-driver-detail-disposition.png', fullPage: true }});
  record('04-driver-detail-disposition.png', 'Driver detail named context + disposition', true);

  // 05 export control on hub with named basis
  await page.goto('{schedule_url}', {{ waitUntil: 'domcontentloaded' }});
  await waitGone(page, 'Loading schedule intelligence');
  const anchors2 = page.locator('section.card').filter({{ has: page.getByRole('heading', {{ name: 'Baseline Anchors' }}) }}).first();
  await anchors2.waitFor({{ state: 'visible', timeout: 120000 }});
  await waitGone(page, 'Loading schedule controls');
  await page.getByRole('button', {{ name: 'Current Contract Baseline', exact: true }}).first().click();
  await waitGone(page, 'Loading schedule controls');
  const controls2 = page.locator('section.card').filter({{ has: page.getByRole('heading', {{ name: 'Schedule Controls' }}) }}).first();
  await controls2.getByText(/Comparing against Current Contract Baseline/i).first().waitFor({{ timeout: 120000 }});
  await page.getByRole('button', {{ name: 'Export Memo', exact: true }}).first().waitFor({{ timeout: 120000 }});
  await assertNotLoading(page, 'export-ui');
  await page.screenshot({{ path: shots + '/05-export-named-basis-selected.png', fullPage: true }});
  record('05-export-named-basis-selected.png', 'Export control with named basis selected', true);

  proof.fully_loaded_required = proof.shots.every(s => s.loaded);
  console.log(JSON.stringify(proof, null, 2));
  await browser.close();
}})();
"""


def wait_http(url: str, timeout_s: int = 120) -> None:
    import time

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status < 500:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(2)
    raise RuntimeError(f"not ready: {url}")


def main() -> int:
    from urllib.parse import quote

    wait_http("http://127.0.0.1:8000/health")
    wait_http("http://127.0.0.1:5173/")
    driver_url = (
        f"{BASE}/projects/{PROJECT}/schedule/driver-detail"
        f"?activity_id={quote(ACTIVITY_ID, safe='')}&comparison_basis=current_contract_baseline&as_of={AS_OF}"
    )
    wb_url = f"{BASE}/projects/{PROJECT}/schedule/workbench?comparison_basis=current_contract_baseline&as_of={AS_OF}"
    script = SCRIPT.format(
        schedule_url=SCHEDULE_URL,
        wb_url=wb_url,
        driver_url=driver_url,
        shots_dir=json.dumps(str(SHOT_DIR).replace("\\", "/")),
        stamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        as_of=AS_OF,
    )
    js_path = EVIDENCE / "_capture_phase13d.cjs"
    js_path.write_text(script, encoding="utf-8")
    pkg = EVIDENCE / "package.json"
    if not pkg.exists():
        pkg.write_text(json.dumps({"dependencies": {"playwright": "^1.49.1"}}, indent=2) + "\n")
        subprocess.run(["npm", "install"], cwd=EVIDENCE, check=True)
    result = subprocess.run(["node", str(js_path)], cwd=EVIDENCE, capture_output=True, text=True)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    print(result.stdout)
    if result.returncode != 0:
        return result.returncode
    stdout = result.stdout.strip()
    start = stdout.rfind('{\n  "stamp"')
    proof = json.loads(stdout[start:]) if start >= 0 else {}
    manifest = SHOT_DIR / "screenshot-proof.json"
    manifest.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    return 0 if proof.get("fully_loaded_required") else 1


if __name__ == "__main__":
    raise SystemExit(main())
