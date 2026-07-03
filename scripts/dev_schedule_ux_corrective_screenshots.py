#!/usr/bin/env python3
"""Capture runtime screenshots for schedule UX corrective evidence (localhost:5173 + copied DB).

Waits for API responses and loaded-state markers before each capture (see scheduleLoadedState recipes).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Callable

try:
    from playwright.sync_api import Page, sync_playwright
except ImportError:
    print("playwright not installed; run: pip install playwright && playwright install chromium", file=sys.stderr)
    raise

ROLE_INIT = "localStorage.setItem('hb-ui-role', 'operator');"

LOADING_MARKERS = [
    "Loading project workspace...",
    "Loading schedule intelligence...",
    "Loading baseline management",
    "Loading schedule workbench...",
    "Loading driver detail...",
    "Loading schedule review dashboard",
]


def wait_loading_markers_hidden(page: Page, timeout_ms: int = 180000) -> None:
    deadline = time.time() + timeout_ms / 1000
    for marker in LOADING_MARKERS:
        remaining = max(1000, int((deadline - time.time()) * 1000))
        locator = page.get_by_text(marker, exact=False)
        try:
            if locator.count() > 0:
                locator.first.wait_for(state="hidden", timeout=remaining)
        except Exception:
            # Marker never appeared or already gone — acceptable.
            pass


def wait_for_response(page: Page, url_part: str, action: Callable[[], None], timeout_ms: int = 180000):
  with page.expect_response(
      lambda r: url_part in r.url and r.request.method == "GET" and r.ok,
      timeout=timeout_ms,
  ):
      action()


def wait_workspace_ready(page: Page, base_url: str, path: str) -> None:
    """Projects list + workspace shell nav must be ready."""

    def navigate() -> None:
        page.goto(f"{base_url}{path}", wait_until="commit", timeout=180000)

    wait_for_response(page, "/api/projects", navigate)
    wait_loading_markers_hidden(page)
    page.get_by_role("button", name="Schedule").wait_for(state="visible", timeout=60000)


def wait_schedule_overview_loaded(page: Page, base_url: str, as_of: str) -> None:
    path = f"/projects/tropical/schedule?as_of={as_of}"
    api_part = f"/api/projects/tropical/schedule?as_of={as_of}"

    def navigate() -> None:
        page.goto(f"{base_url}{path}", wait_until="commit", timeout=180000)

    wait_for_response(page, api_part, navigate)
    wait_loading_markers_hidden(page)
    page.locator('[data-testid="manage-baselines-primary-action"]').wait_for(state="visible", timeout=60000)
    page.locator('[data-testid="baseline-management-section"]').wait_for(state="visible", timeout=60000)
    page.get_by_text("Primary Actions", exact=False).first.wait_for(state="visible", timeout=30000)
    # Confirm as-of context rendered in header line.
    page.get_by_text(as_of, exact=False).first.wait_for(state="visible", timeout=30000)


def wait_baselines_page_loaded(page: Page, base_url: str, as_of: str) -> None:
    path = f"/projects/tropical/schedule/baselines?as_of={as_of}"
    api_part = "/api/projects/tropical/schedule/baselines"

    def navigate() -> None:
        page.goto(f"{base_url}{path}", wait_until="commit", timeout=180000)

    wait_for_response(page, api_part, navigate)
    wait_loading_markers_hidden(page)
    page.locator('[data-testid="baseline-management-page"]').wait_for(state="visible", timeout=60000)
    page.get_by_role("heading", name="Manage Baselines").wait_for(state="visible", timeout=30000)


def wait_workbench_loaded(page: Page, base_url: str, as_of: str) -> None:
    path = f"/projects/tropical/schedule/workbench?as_of={as_of}"
    api_part = "/api/projects/tropical/schedule/review-items"

    def navigate() -> None:
        page.goto(f"{base_url}{path}", wait_until="commit", timeout=180000)

    wait_for_response(page, api_part, navigate)
    wait_loading_markers_hidden(page)
    page.get_by_role("heading", name="Schedule Workbench").wait_for(state="visible", timeout=60000)


def wait_import_loaded(page: Page, base_url: str) -> None:
    path = "/projects/tropical/schedule/import"
    wait_workspace_ready(page, base_url, path)
    page.get_by_role("heading", name="Upload schedule update").wait_for(state="visible", timeout=30000)
    page.locator('input[type="file"]').first.wait_for(state="attached", timeout=30000)


def wait_driver_index_loaded(page: Page, base_url: str, path: str) -> None:
    wait_workspace_ready(page, base_url, path)
    page.locator('h3.section-title:has-text("Activity Drivers")').wait_for(state="visible", timeout=30000)


def capture_loading_state(page: Page, base_url: str, out: Path) -> None:
    """Mid-fetch refreshing banner when as_of changes in-page (not full navigation)."""
    wait_schedule_overview_loaded(page, base_url, "2026-06-22")

    def delay_schedule(route):
        time.sleep(4.0)
        route.continue_()

    page.route("**/api/projects/tropical/schedule?as_of=2026-06-29*", delay_schedule)
    date_input = page.locator('input[type="date"]').first
    date_input.wait_for(state="visible", timeout=30000)
    date_input.fill("2026-06-29")

    page.locator('[data-testid="schedule-refreshing-banner"]').wait_for(state="visible", timeout=20000)
    page.locator('[data-testid="manage-baselines-primary-action"]').wait_for(state="visible", timeout=5000)
    page.get_by_text("Refreshing schedule data", exact=False).first.wait_for(state="visible", timeout=5000)
    page.screenshot(path=str(out / "04-asof-refresh-loading-state.png"), full_page=True)
    print("captured 04-asof-refresh-loading-state.png")

    page.unroute("**/api/projects/tropical/schedule?as_of=2026-06-29*", delay_schedule)
    wait_schedule_overview_loaded(page, base_url, "2026-06-29")
    page.locator('[data-testid="schedule-refreshing-banner"]').wait_for(state="hidden", timeout=120000)
    page.get_by_text("TWNU19", exact=False).first.wait_for(state="visible", timeout=30000)
    page.screenshot(path=str(out / "05-post-refresh-trends-state-asof-2026-06-29.png"), full_page=True)
    print("captured 05-post-refresh-trends-state-asof-2026-06-29.png")


def write_proof(out: Path, entries: list[dict]) -> None:
    proof_path = out.parent / "screenshot-loaded-state-proof.json"
    proof_path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    print("wrote", proof_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True, help="Absolute path to screenshots directory")
    parser.add_argument("--base-url", default="http://127.0.0.1:5173")
    args = parser.parse_args()
    out = Path(args.out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    proof: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.add_init_script(ROLE_INIT)

        # 01 overview
        wait_schedule_overview_loaded(page, args.base_url, "2026-06-22")
        page.screenshot(path=str(out / "01-overview-top-asof-2026-06-22.png"), full_page=True)
        print("captured 01-overview-top-asof-2026-06-22.png")
        proof.append({"file": "01-overview-top-asof-2026-06-22.png", "loaded": True, "markers": "schedule overview + Primary Actions"})

        # 02 dropdown (overview already loaded)
        page.get_by_role("button", name="Schedule").click(timeout=30000)
        page.get_by_role("link", name="Manage Baselines").wait_for(state="visible", timeout=10000)
        page.screenshot(path=str(out / "02-schedule-dropdown-open-manage-baselines.png"), full_page=True)
        print("captured 02-schedule-dropdown-open-manage-baselines.png")
        proof.append({"file": "02-schedule-dropdown-open-manage-baselines.png", "loaded": True, "markers": "dropdown Manage Baselines link"})

        # 03 baselines page
        wait_baselines_page_loaded(page, args.base_url, "2026-06-22")
        page.screenshot(path=str(out / "03-baseline-management-visible.png"), full_page=True)
        print("captured 03-baseline-management-visible.png")
        proof.append({"file": "03-baseline-management-visible.png", "loaded": True, "markers": "baseline-management-page"})

        # 06 import
        wait_import_loaded(page, args.base_url)
        page.screenshot(path=str(out / "06-import-schedule-route.png"), full_page=True)
        print("captured 06-import-schedule-route.png")
        proof.append({"file": "06-import-schedule-route.png", "loaded": True, "markers": "Upload schedule update + Choose File"})

        # 07 workbench
        wait_workbench_loaded(page, args.base_url, "2026-06-29")
        page.screenshot(path=str(out / "07-review-workbench-route.png"), full_page=True)
        print("captured 07-review-workbench-route.png")
        proof.append({"file": "07-review-workbench-route.png", "loaded": True, "markers": "Schedule Workbench heading"})

        # 08 driver detail empty
        wait_driver_index_loaded(page, args.base_url, "/projects/tropical/schedule/driver-detail")
        page.screenshot(path=str(out / "08-driver-detail-empty-state.png"), full_page=True)
        print("captured 08-driver-detail-empty-state.png")
        proof.append({"file": "08-driver-detail-empty-state.png", "loaded": True, "markers": "Activity Drivers index"})

        # 09 activity drivers
        wait_driver_index_loaded(page, args.base_url, "/projects/tropical/schedule/drivers")
        page.screenshot(path=str(out / "09-activity-drivers-empty-state.png"), full_page=True)
        print("captured 09-activity-drivers-empty-state.png")
        proof.append({"file": "09-activity-drivers-empty-state.png", "loaded": True, "markers": "Activity Drivers index"})

        # 04 + 05 loading sequence
        capture_loading_state(page, args.base_url, out)
        proof.append({"file": "04-asof-refresh-loading-state.png", "loaded": True, "markers": "schedule-refreshing-banner visible"})
        proof.append({"file": "05-post-refresh-trends-state-asof-2026-06-29.png", "loaded": True, "markers": "as_of 2026-06-29 settled, refreshing banner hidden"})

        browser.close()

    write_proof(out, proof)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
