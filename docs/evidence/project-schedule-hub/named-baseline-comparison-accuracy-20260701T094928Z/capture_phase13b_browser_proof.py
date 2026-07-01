#!/usr/bin/env python3
"""Phase 13B browser screenshots — 9 shots, strict loaded gates, screenshot-proof.json."""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent
SHOT_DIR = EVIDENCE / "12-browser-screenshots"
SHOT_DIR.mkdir(parents=True, exist_ok=True)

AS_OF = "2026-07-03"
BASE = "http://127.0.0.1:5173"
PROJECT = "tropical"
SCHEDULE_URL = f"{BASE}/projects/{PROJECT}/schedule?as_of={AS_OF}"


def _activity_id() -> str:
    sel = EVIDENCE / "13b-driver-activity-selection.json"
    if sel.exists():
        return json.loads(sel.read_text())["activity_id"]
    return "FILTER-OUT-50"


def _driver_url(activity_id: str, basis: str) -> str:
    from urllib.parse import quote

    return (
        f"{BASE}/projects/{PROJECT}/schedule/driver-detail"
        f"?activity_id={quote(activity_id, safe='')}&comparison_basis={basis}&as_of={AS_OF}"
    )


def _workbench_url(basis: str) -> str:
    return f"{BASE}/projects/{PROJECT}/schedule/workbench?comparison_basis={basis}&as_of={AS_OF}"


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

async function waitHub(page) {{
  await page.goto('{schedule_url}', {{ waitUntil: 'domcontentloaded', timeout: 120000 }});
  await waitGone(page, 'Loading schedule intelligence');
  const anchors = page.locator('section.card').filter({{ has: page.getByRole('heading', {{ name: 'Baseline Anchors' }}) }}).first();
  await anchors.waitFor({{ state: 'visible', timeout: 120000 }});
  await waitGone(page, 'Loading baseline selections');
  for (const t of ['Current Contract Baseline', 'Previous Progress Update Baseline', 'Secondary Progress Update Baseline']) {{
    await anchors.getByText(t, {{ exact: true }}).waitFor({{ timeout: 120000 }});
  }}
  if ((await page.getByText('Project workspace could not be loaded', {{ exact: false }}).count()) > 0)
    throw new Error('hub: fatal load error');
}}

async function selectBasis(page, label) {{
  const btn = page.getByRole('button', {{ name: label, exact: true }});
  await btn.first().click();
  await page.waitForTimeout(2500);
  await waitGone(page, 'Loading schedule controls');
  await assertNotLoading(page, 'controls-' + label);
}}

async function waitControlsNamed(page, pattern) {{
  const controls = page.locator('section.card').filter({{ has: page.getByRole('heading', {{ name: 'Schedule Controls' }}) }}).first();
  await controls.waitFor({{ state: 'visible', timeout: 120000 }});
  await controls.getByText(pattern, {{ exact: false }}).first().waitFor({{ timeout: 120000 }});
  await assertNotLoading(page, 'controls');
}}

async function waitWorkbench(page, basisPattern) {{
  await page.getByRole('heading', {{ name: 'Schedule Workbench' }}).waitFor({{ timeout: 120000 }});
  await waitGone(page, 'Loading schedule workbench');
  await page.getByText(basisPattern, {{ exact: false }}).first().waitFor({{ timeout: 120000 }});
  await assertNotLoading(page, 'workbench');
}}

async function waitDriver(page, basisPattern) {{
  await waitGone(page, 'Loading driver detail');
  await page.getByText('Side-by-Side Movement', {{ exact: true }}).waitFor({{ timeout: 120000 }});
  await page.getByText(basisPattern, {{ exact: false }}).first().waitFor({{ timeout: 120000 }});
  await assertNotLoading(page, 'driver');
}}

(async () => {{
  const browser = await chromium.launch();
  const page = await browser.newPage({{ viewport: {{ width: 1440, height: 900 }} }});
  await page.addInitScript(() => localStorage.setItem('hb-ui-role', 'operator'));
  const shots = {shots_dir};
  const proof = {{ stamp: '{stamp}', as_of: '{as_of}', shots: [] }};

  function record(file, surface, loaded, extra = {{}}) {{
    proof.shots.push({{ file, surface, loaded, ...extra }});
  }}

  // 01 hub
  await waitHub(page);
  await page.screenshot({{ path: shots + '/01-schedule-hub-named-baselines.png', fullPage: true }});
  record('01-schedule-hub-named-baselines.png', 'Schedule hub + Baseline Anchors', true);

  // 02 contract controls
  await selectBasis(page, 'Current Contract Baseline');
  await waitControlsNamed(page, /Comparing against Current Contract Baseline/i);
  await page.screenshot({{ path: shots + '/02-controls-current-contract-baseline.png', fullPage: true }});
  record('02-controls-current-contract-baseline.png', 'Controls current_contract_baseline', true);

  // 03 previous progress controls
  await waitHub(page);
  await selectBasis(page, 'Previous Progress Update Baseline');
  await waitControlsNamed(page, /Comparing against Previous Progress Update Baseline/i);
  await page.screenshot({{ path: shots + '/03-controls-previous-progress-baseline.png', fullPage: true }});
  record('03-controls-previous-progress-baseline.png', 'Controls previous_progress_update_baseline', true);

  // 04 secondary controls
  await waitHub(page);
  await selectBasis(page, 'Secondary Progress Update Baseline');
  await waitControlsNamed(page, /Comparing against Secondary Progress Update Baseline/i);
  await page.screenshot({{ path: shots + '/04-controls-secondary-progress-baseline.png', fullPage: true }});
  record('04-controls-secondary-progress-baseline.png', 'Controls secondary_progress_update_baseline', true);

  // 05 controls disposition — review_item_id on control card
  await waitHub(page);
  await selectBasis(page, 'Current Contract Baseline');
  await waitControlsNamed(page, /Comparing against Current Contract Baseline/i);
  const ctrl = page.locator('section.card').filter({{ has: page.getByRole('heading', {{ name: 'Schedule Controls' }}) }}).first();
  const dispositionVisible = (await ctrl.getByText(/watching|reviewed|dismissed/i).count()) > 0
    || (await ctrl.locator('a[href*="workbench"]').count()) > 0
    || (await ctrl.getByText(/psnbri-|psri-/i).count()) > 0;
  if (!dispositionVisible) throw new Error('controls disposition markers missing');
  await page.screenshot({{ path: shots + '/05-controls-disposition-item.png', fullPage: true }});
  record('05-controls-disposition-item.png', 'Controls item linked to review disposition', true);

  // 06 workbench named filter
  await page.goto('{wb_contract}', {{ waitUntil: 'domcontentloaded' }});
  await waitWorkbench(page, /Comparing against Current Contract Baseline|current contract baseline/i);
  await page.screenshot({{ path: shots + '/06-workbench-named-baseline-filter.png', fullPage: true }});
  record('06-workbench-named-baseline-filter.png', 'Workbench named-baseline filter', true);

  // 07 driver named context
  await page.goto('{driver_contract}', {{ waitUntil: 'domcontentloaded' }});
  await waitDriver(page, /Comparing against Current Contract Baseline/i);
  await page.screenshot({{ path: shots + '/07-driver-detail-named-baseline.png', fullPage: true }});
  record('07-driver-detail-named-baseline.png', 'Driver detail named baseline context', true);

  // 08 driver disposition — not on API/UI; attempt, mark loaded false if absent
  let driverDispLoaded = false;
  try {{
    const badge = page.getByText(/watching|reviewed|dismissed/i);
    if ((await badge.count()) > 0) {{
      await badge.first().waitFor({{ timeout: 5000 }});
      driverDispLoaded = true;
    }}
  }} catch (e) {{}}
  await page.screenshot({{ path: shots + '/08-driver-detail-disposition.png', fullPage: true }});
  record('08-driver-detail-disposition.png', 'Driver detail disposition (if present)', driverDispLoaded,
    {{ limitation: driverDispLoaded ? null : 'P2 — Driver Detail disposition fields not implemented' }});

  // 09 scope isolation — prior_update vs named secondary movement labels
  await waitHub(page);
  const controlsCard = page.locator('section.card').filter({{ has: page.getByRole('heading', {{ name: 'Schedule Controls' }}) }}).first();
  await selectBasis(page, 'Prior Update');
  await waitControlsNamed(page, /Comparing against Prior Update/i);
  const priorText = await controlsCard.getByText(/finish.*later|moved later/i).first().textContent().catch(() => '');
  await selectBasis(page, 'Secondary Progress Update Baseline');
  await waitControlsNamed(page, /Comparing against Secondary Progress Update Baseline/i);
  const namedText = await controlsCard.getByText(/finish.*later|moved later/i).first().textContent().catch(() => '');
  if (!priorText || !namedText) throw new Error('scope isolation movement text missing');
  await page.screenshot({{ path: shots + '/09-scope-isolation-prior-vs-named.png', fullPage: true }});
  record('09-scope-isolation-prior-vs-named.png', 'prior_update vs named-baseline scope isolation', true,
    {{ prior_movement_snippet: priorText.slice(0, 120), named_movement_snippet: namedText.slice(0, 120) }});

  proof.fully_loaded_required = proof.shots.filter(s => s.file !== '08-driver-detail-disposition.png').every(s => s.loaded);
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
    activity_id = _activity_id()
    wait_http("http://127.0.0.1:8000/health")
    wait_http("http://127.0.0.1:5173/")

    script = SCRIPT.format(
        schedule_url=SCHEDULE_URL,
        wb_contract=_workbench_url("current_contract_baseline"),
        driver_contract=_driver_url(activity_id, "current_contract_baseline"),
        shots_dir=json.dumps(str(SHOT_DIR).replace("\\", "/")),
        stamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        as_of=AS_OF,
    )
    js_path = EVIDENCE / "_capture_phase13b.cjs"
    js_path.write_text(script, encoding="utf-8")
    result = subprocess.run(["node", str(js_path)], cwd=EVIDENCE, capture_output=True, text=True)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    print(result.stdout)
    if result.returncode != 0:
        return result.returncode
    stdout = result.stdout.strip()
    start = stdout.rfind('{\n  "stamp"')
    proof = json.loads(stdout[start:]) if start >= 0 else {}
    manifest = EVIDENCE / "12-browser-screenshots" / "screenshot-proof.json"
    manifest.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {manifest}")
    return 0 if proof.get("fully_loaded_required") else 1


if __name__ == "__main__":
    raise SystemExit(main())
