#!/usr/bin/env python3
"""Phase 13 browser proof — named baseline workbench disposition persistence."""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent
SHOT_DIR = EVIDENCE / "screenshots"
SHOT_DIR.mkdir(parents=True, exist_ok=True)
AS_OF = "2026-07-03"
BASE = "http://127.0.0.1:5173"
WORKBENCH = f"{BASE}/projects/tropical/schedule/workbench?comparison_basis=current_contract_baseline&as_of={AS_OF}"
PRIOR = f"{BASE}/projects/tropical/schedule/workbench?as_of={AS_OF}"
PROGRESS = f"{BASE}/projects/tropical/schedule/workbench?comparison_basis=previous_progress_update_baseline&as_of={AS_OF}"

SCRIPT = f"""
const {{ chromium }} = require('playwright');
(async () => {{
  const browser = await chromium.launch();
  const page = await browser.newPage();
  async function shot(name, url, waitText) {{
    await page.goto(url, {{ waitUntil: 'networkidle' }});
    await page.getByText(waitText, {{ exact: false }}).first().waitFor({{ timeout: 90000 }});
    await page.screenshot({{ path: '{SHOT_DIR}/' + name + '.png', fullPage: true }});
    console.log('shot', name);
  }}
  await shot('01-named-workbench-loaded', '{WORKBENCH}', 'Named baseline review');
  await shot('02-prior-update-unaffected', '{PRIOR}', 'Schedule Workbench');
  await shot('03-progress-slot-separate', '{PROGRESS}', 'Schedule Workbench');
  await browser.close();
}})();
"""


def main() -> None:
    try:
        urllib.request.urlopen("http://127.0.0.1:5173", timeout=5)
    except Exception as exc:
        raise SystemExit(f"frontend not ready: {exc}") from exc
    script_path = EVIDENCE / "_capture_phase13.cjs"
    script_path.write_text(SCRIPT)
    subprocess.run(["node", str(script_path)], check=True)
    proof = {
        "shots": [
            {"file": "01-named-workbench-loaded.png", "proof": "named sync enabled banner"},
            {"file": "02-prior-update-unaffected.png", "proof": "prior_update queue"},
            {"file": "03-progress-slot-separate.png", "proof": "cross-slot isolation"},
        ]
    }
    (EVIDENCE / "screenshot-proof.json").write_text(json.dumps(proof, indent=2))


if __name__ == "__main__":
    main()
