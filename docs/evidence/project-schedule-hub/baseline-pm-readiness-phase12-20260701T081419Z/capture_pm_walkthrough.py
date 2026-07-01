#!/usr/bin/env python3
"""Capture Phase 12 PM walkthrough screenshots with loaded-state gates."""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

STAMP = "20260701T081419Z"
EVIDENCE = Path(__file__).resolve().parent
SHOT_DIR = EVIDENCE / "screenshots" / (sys.argv[1] if len(sys.argv) > 1 else "post-fix")
SHOT_DIR.mkdir(parents=True, exist_ok=True)

AS_OF = "2026-07-01"
BASE = "http://127.0.0.1:5173"
SCHEDULE_URL = f"{BASE}/projects/tropical/schedule?as_of={AS_OF}"
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

const LOADING_MARKERS = {{
  anchors: ['Loading baseline selections'],
  controls: ['Loading schedule controls'],
  workbench: ['Loading schedule workbench'],
  driver: ['Loading driver detail'],
  fatal: ['Project workspace could not be loaded'],
}};

async function assertSurfaceClear(page, markers, label) {{
  for (const marker of markers) {{
    const count = await page.getByText(marker, {{ exact: false }}).count();
    if (count > 0) {{
      throw new Error(`${{label}}: still showing "${{marker}}"`);
    }}
  }}
}}

async function waitUntilGone(page, text, timeoutMs = 90000) {{
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {{
    if ((await page.getByText(text, {{ exact: false }}).count()) === 0) return;
    await page.waitForTimeout(500);
  }}
  throw new Error(`Timed out waiting for "${{text}}" to disappear`);
}}
async function assertNotLoading(page, label) {{
  await assertSurfaceClear(page, [
    ...LOADING_MARKERS.anchors,
    ...LOADING_MARKERS.controls,
    ...LOADING_MARKERS.workbench,
    ...LOADING_MARKERS.driver,
    ...LOADING_MARKERS.fatal,
  ], label);
}}

async function waitForBaselineAnchorsLoaded(page) {{
  const anchors = page.locator('section.card').filter({{
    has: page.getByRole('heading', {{ name: 'Baseline Anchors' }}),
  }}).first();
  await anchors.waitFor({{ state: 'visible', timeout: 90000 }});
  await waitUntilGone(page, 'Loading baseline selections');
  await anchors.getByText('Current Contract Baseline', {{ exact: true }}).waitFor();
  await anchors.getByText('Previous Progress Update Baseline', {{ exact: true }}).waitFor();
  await anchors.getByText('Secondary Progress Update Baseline', {{ exact: true }}).waitFor();
  await anchors.locator('p').filter({{ hasText: /TWNU07/i }}).first().waitFor({{ timeout: 90000 }});
  await anchors.locator('p').filter({{ hasText: /TWNU18/i }}).first().waitFor({{ timeout: 90000 }});
  await anchors.locator('p').filter({{ hasText: /TWNU14/i }}).first().waitFor({{ timeout: 90000 }});
  const missing = await anchors.getByText('Select a prior schedule update for this anchor.').count();
  if (missing > 0) throw new Error('baseline anchors: missing slot still visible');
  await assertSurfaceClear(page, [...LOADING_MARKERS.anchors, ...LOADING_MARKERS.fatal], 'baseline anchors');
}}

async function waitForControlsLoaded(page, named = false) {{
  const controls = page.locator('section.card').filter({{
    has: page.getByRole('heading', {{ name: 'Schedule Controls' }}),
  }}).first();
  await controls.waitFor({{ state: 'visible', timeout: 90000 }});
  await waitUntilGone(page, 'Loading schedule controls');
  await assertSurfaceClear(page, [...LOADING_MARKERS.fatal], 'schedule controls');
  if (named) {{
    await controls.getByText(/Comparing against Current Contract Baseline/i).waitFor({{ timeout: 90000 }});
    await controls.getByText(/TWNU07/i).first().waitFor({{ timeout: 90000 }});
  }} else {{
    await controls.getByText(/Comparing against Prior Update/i).waitFor({{ timeout: 90000 }});
  }}
}}

async function waitForWorkbenchLoaded(page) {{
  await page.getByRole('heading', {{ name: 'Schedule Workbench' }}).waitFor({{ timeout: 90000 }});
  await waitUntilGone(page, 'Loading schedule workbench');
  await page.getByText('Named baseline preview — read only', {{ exact: false }}).waitFor({{ timeout: 90000 }});
  await page.getByText(/Comparing against Current Contract Baseline/i).first().waitFor({{ timeout: 90000 }});
  await page.getByText('Candidate change driver', {{ exact: false }}).first().waitFor({{ timeout: 90000 }});
  await assertSurfaceClear(page, [...LOADING_MARKERS.fatal], 'workbench');
}}

async function waitForDriverLoaded(page) {{
  await waitUntilGone(page, 'Loading driver detail');
  await page.getByRole('heading', {{ name: /FAB\\/DEL EXTERIOR LIGHT FIXTURES/i }}).waitFor({{ timeout: 90000 }});
  await page.getByText('Side-by-Side Movement', {{ exact: true }}).waitFor({{ timeout: 90000 }});
  await page.getByText(/Comparing against Current Contract Baseline/i).first().waitFor({{ timeout: 90000 }});
  await assertSurfaceClear(page, [...LOADING_MARKERS.fatal], 'driver detail');
}}

(async () => {{
  const browser = await chromium.launch();
  const page = await browser.newPage({{ viewport: {{ width: 1440, height: 900 }} }});
  await page.addInitScript(() => localStorage.setItem('hb-ui-role', 'operator'));
  const shots = {json.dumps(str(SHOT_DIR))};
  const proof = {{ method: 'playwright', shots: [] }};

  // 01 — Schedule hub with three selected Tropical baselines
  await page.goto('{SCHEDULE_URL}', {{ waitUntil: 'domcontentloaded' }});
  await waitForBaselineAnchorsLoaded(page);
  await waitForControlsLoaded(page, false);
  await waitForBaselineAnchorsLoaded(page);
  await page.locator('section.card').filter({{
    has: page.getByRole('heading', {{ name: 'Baseline Anchors' }}),
  }}).first().scrollIntoViewIfNeeded();
  await page.waitForTimeout(500);
  await page.screenshot({{ path: shots + '/01-schedule-hub-baseline-anchors.png', fullPage: true }});
  proof.shots.push({{ file: '01-schedule-hub-baseline-anchors.png', surface: 'schedule hub + baseline anchors', loaded: true }});

  // 02 — Controls with Current Contract Baseline + comparison context
  await page.getByRole('button', {{ name: 'Current Contract Baseline', exact: true }}).click();
  await waitForControlsLoaded(page, true);
  await page.screenshot({{ path: shots + '/02-controls-named-baseline.png', fullPage: true }});
  proof.shots.push({{ file: '02-controls-named-baseline.png', surface: 'schedule controls named baseline', loaded: true }});

  // 03 — Named Workbench read-only + review cues
  await page.goto('{WORKBENCH_URL}', {{ waitUntil: 'domcontentloaded' }});
  await waitForWorkbenchLoaded(page);
  await page.screenshot({{ path: shots + '/03-workbench-named-baseline.png', fullPage: true }});
  proof.shots.push({{ file: '03-workbench-named-baseline.png', surface: 'named workbench', loaded: true }});

  // 04 — Driver detail slash activity
  await page.goto('{DRIVER_URL}', {{ waitUntil: 'domcontentloaded' }});
  await waitForDriverLoaded(page);
  await page.screenshot({{ path: shots + '/04-driver-detail-slash-activity.png', fullPage: true }});
  proof.shots.push({{ file: '04-driver-detail-slash-activity.png', surface: 'driver detail FAB/DEL-10', loaded: true }});

  // 05 — Back navigation preserves context
  await page.getByRole('link', {{ name: 'Workbench' }}).click();
  await page.waitForURL('**/schedule/workbench**', {{ timeout: 30000 }});
  await waitForWorkbenchLoaded(page);
  const backUrl = page.url();
  if (!backUrl.includes('comparison_basis=current_contract_baseline') || !backUrl.includes('as_of={AS_OF}')) {{
    throw new Error('Back navigation lost comparison_basis or as_of: ' + backUrl);
  }}
  await page.screenshot({{ path: shots + '/05-back-to-workbench.png', fullPage: true }});
  proof.shots.push({{ file: '05-back-to-workbench.png', surface: 'back navigation', loaded: true, url: backUrl }});

  // 06 — Missing baseline via mocked controls API (no DB mutation)
  await page.route('**/api/projects/tropical/schedule/controls**', async (route) => {{
    const url = route.request().url();
    if (url.includes('comparison_basis=current_contract_baseline')) {{
      return route.fulfill({{
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({{
          available: false,
          reason: 'baseline_not_selected',
          comparison_basis: 'current_contract_baseline',
          baseline_context: {{ slot_label: 'Current Contract Baseline', selection_status: 'missing' }},
        }}),
      }});
    }}
    return route.continue();
  }});
  await page.goto('{SCHEDULE_URL}', {{ waitUntil: 'domcontentloaded' }});
  await waitForBaselineAnchorsLoaded(page);
  await page.getByRole('button', {{ name: 'Current Contract Baseline', exact: true }}).click();
  await waitUntilGone(page, 'Loading schedule controls');
  await page.getByText(/Select a prior schedule update for Current Contract Baseline in Baseline Anchors below/i)
    .waitFor({{ timeout: 90000 }});
  await assertSurfaceClear(page, [...LOADING_MARKERS.fatal], 'missing baseline controls');
  await page.screenshot({{ path: shots + '/06-missing-baseline-controls.png', fullPage: true }});
  proof.shots.push({{ file: '06-missing-baseline-controls.png', surface: 'missing baseline (mocked API)', loaded: true, proof: 'fixture' }});

  console.log(JSON.stringify(proof, null, 2));
  await browser.close();
}})();
"""


def wait_http(url: str, timeout_s: int = 60) -> None:
    import time

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(2)
    raise RuntimeError(f"Service not ready: {url}")


def main() -> int:
    wait_http("http://127.0.0.1:8000/health")
    wait_http("http://127.0.0.1:5173/")

    tmpdir = Path("/tmp/hb-phase12-playwright")
    tmpdir.mkdir(exist_ok=True)
    js_path = tmpdir / "capture-loaded.js"
    js_path.write_text(SCRIPT)
    if not (tmpdir / "node_modules" / "playwright").exists():
        subprocess.run(["npm", "init", "-y"], cwd=tmpdir, capture_output=True)
        subprocess.run(["npm", "install", "playwright@1.49.1"], cwd=tmpdir, capture_output=True)
        subprocess.run(["npx", "playwright", "install", "chromium"], cwd=tmpdir, capture_output=True)

    result = subprocess.run(["node", str(js_path)], cwd=tmpdir, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if result.returncode != 0:
        return result.returncode

    # proof JSON is the last stdout block
    stdout = result.stdout.strip()
    try:
        proof = json.loads(stdout)
    except json.JSONDecodeError:
        proof_start = stdout.rfind('{\n  "method"')
        proof = json.loads(stdout[proof_start:]) if proof_start >= 0 else {}
    manifest_path = EVIDENCE / "screenshot-proof.json"
    manifest_path.write_text(json.dumps(proof, indent=2) + "\n")
    print(f"Wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
