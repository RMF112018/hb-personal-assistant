#!/usr/bin/env python3
"""Phase 18 portfolio dashboard browser screenshots (fully loaded states)."""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent
ROOT = EVIDENCE.parents[3]
FIXTURE_DB = EVIDENCE / "fixture-phase18-portfolio.db"
BASE = "http://127.0.0.1:5173"
DASHBOARD = f"{BASE}/projects/all/schedule/review"
API_PORT = 8001


def wait_http(url: str, timeout_s: int = 120) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status < 500:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(1)
    raise RuntimeError(f"not ready: {url}")


def main() -> int:
    subprocess.run([sys.executable, str(EVIDENCE / "seed_phase18_fixture_db.py")], check=True, cwd=ROOT)
    api_proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import uvicorn; "
                "from hb_assistant.construction.analytics import create_app; "
                f"app = create_app(db_path={str(FIXTURE_DB)!r}); "
                f"uvicorn.run(app, host='127.0.0.1', port={API_PORT}, log_level='warning')"
            ),
        ],
        cwd=ROOT,
        env={
            **dict(__import__("os").environ),
            "PYTHONPATH": f"{ROOT / 'src'}:{ROOT / 'subrepos/construction-financial-review/src'}",
        },
    )
    vite_proc = subprocess.Popen(
        [
            "npx",
            "vite",
            "--host",
            "127.0.0.1",
            "--port",
            "5173",
            "--config",
            str(ROOT / "frontend" / "vite.phase18.config.ts"),
        ],
        cwd=ROOT / "frontend",
    )
    try:
        wait_http(f"http://127.0.0.1:{API_PORT}/health")
        wait_http(BASE)
        result = subprocess.run(["node", str(EVIDENCE / "capture_phase18_browser_proof.cjs")], cwd=EVIDENCE, capture_output=True, text=True)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        print(result.stdout)
        return result.returncode
    finally:
        vite_proc.terminate()
        api_proc.terminate()
        vite_proc.wait(timeout=10)
        api_proc.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
