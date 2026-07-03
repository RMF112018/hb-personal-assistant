#!/usr/bin/env python3
"""Capture runtime screenshots for schedule UX corrective evidence (localhost:5173 + copied DB)."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("playwright not installed; run: pip install playwright && playwright install chromium", file=sys.stderr)
    raise

ROLE_INIT = "localStorage.setItem('hb-ui-role', 'operator');"


def capture_loading_state(page, base_url: str, out: Path) -> None:
    """Capture mid-fetch refreshing banner during as_of navigation."""
    page.goto(f"{base_url}/projects/tropical/schedule?as_of=2026-06-22", wait_until="domcontentloaded", timeout=120000)
    page.wait_for_timeout(2000)

    def delay_schedule(route):
        time.sleep(2.5)
        route.continue_()

    page.route("**/api/projects/tropical/schedule?as_of=2026-06-29*", delay_schedule)
    page.goto(f"{base_url}/projects/tropical/schedule?as_of=2026-06-29", wait_until="commit", timeout=120000)
    try:
        page.locator('[data-testid="schedule-refreshing-banner"]').wait_for(state="visible", timeout=8000)
    except Exception:
        page.wait_for_timeout(1500)
    page.screenshot(path=str(out / "04-asof-refresh-loading-state.png"), full_page=True)
    print("captured 04-asof-refresh-loading-state.png")
    page.unroute("**/api/projects/tropical/schedule?as_of=2026-06-29*", delay_schedule)
    page.goto(f"{base_url}/projects/tropical/schedule?as_of=2026-06-29", wait_until="domcontentloaded", timeout=120000)
    page.wait_for_timeout(2500)
    page.screenshot(path=str(out / "05-post-refresh-trends-state-asof-2026-06-29.png"), full_page=True)
    print("captured 05-post-refresh-trends-state-asof-2026-06-29.png")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True, help="Absolute path to screenshots directory")
    parser.add_argument("--base-url", default="http://127.0.0.1:5173")
    args = parser.parse_args()
    out = Path(args.out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    shots: list[tuple[str, str, str | None]] = [
        ("01-overview-top-asof-2026-06-22.png", "/projects/tropical/schedule?as_of=2026-06-22", None),
        ("02-schedule-dropdown-open-manage-baselines.png", "/projects/tropical/schedule?as_of=2026-06-22", "dropdown"),
        ("03-baseline-management-visible.png", "/projects/tropical/schedule/baselines?as_of=2026-06-22", None),
        ("06-import-schedule-route.png", "/projects/tropical/schedule/import", None),
        ("07-review-workbench-route.png", "/projects/tropical/schedule/workbench?as_of=2026-06-29", None),
        ("08-driver-detail-empty-state.png", "/projects/tropical/schedule/driver-detail", None),
        ("09-activity-drivers-empty-state.png", "/projects/tropical/schedule/drivers", None),
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.add_init_script(ROLE_INIT)

        for name, path, mode in shots:
            page.goto(f"{args.base_url}{path}", wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(2000)
            if mode == "dropdown":
                page.get_by_role("button", name="Schedule").click(timeout=60000)
                page.wait_for_timeout(500)
            page.screenshot(path=str(out / name), full_page=True)
            print("captured", name)

        capture_loading_state(page, args.base_url, out)
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
