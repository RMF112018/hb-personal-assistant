#!/usr/bin/env python3
"""Phase 18 live DB GET-only smoke — portfolio schedule review dashboard."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EVIDENCE = Path(__file__).resolve().parent
ROOT = EVIDENCE.parents[3]

# Tables whose row counts should remain unchanged during GET-only smoke.
_MUTATION_WATCH_TABLES = (
    "schedule_file_imports",
    "procore_ep_projects",
    "project_schedule_review_items",
    "project_schedule_review_item_events",
    "schedule_quality_evaluation_runs",
    "project_schedule_series_membership",
    "project_schedule_named_baseline_review_items",
)

_FORBIDDEN_LANGUAGE = re.compile(
    r"\b(claim|liability|responsibility|fault|compensable|entitlement|delay damages|caused|causation|forensic)\b",
    re.IGNORECASE,
)

_GET_ENDPOINTS: list[tuple[str, str, dict[str, str] | None]] = [
    ("18-live-dashboard-api.json", "/api/projects/schedule-review-dashboard", None),
    ("19-live-dashboard-filter-missing.json", "/api/projects/schedule-review-dashboard", {"status": "missing"}),
    ("20-live-dashboard-filter-stale.json", "/api/projects/schedule-review-dashboard", {"status": "stale"}),
    ("21-live-dashboard-filter-needs-review.json", "/api/projects/schedule-review-dashboard", {"status": "needs_review"}),
    (
        "22-live-dashboard-filter-operator-action.json",
        "/api/projects/schedule-review-dashboard",
        {"status": "operator_action_required"},
    ),
    (
        "23-live-portfolio-export.md",
        "/api/projects/schedule-review-dashboard/export",
        {"format": "markdown"},
    ),
]

_VIEWER_HEADERS = {"X-HB-UI-Role": "viewer"}
_API_PORT = 8002
_VITE_PORT = 5174


def _setup_import_path() -> None:
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "subrepos/construction-financial-review/src"))


def resolve_live_db_path() -> Path:
    from hb_assistant.config.path_policy import PathPolicy

    raw = os.environ.get("HB_ASSISTANT_DB_PATH")
    db_path = Path(raw) if raw else PathPolicy().get_db_path()
    if not db_path.is_file():
        raise FileNotFoundError(f"live DB not found: {db_path}")
    return db_path.resolve()


def _related_db_paths(db_path: Path) -> list[Path]:
    paths = [db_path]
    for suffix in ("-wal", "-shm"):
        candidate = Path(str(db_path) + suffix)
        if candidate.exists():
            paths.append(candidate)
    return paths


def _file_metadata(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    stat = path.stat()
    return {
        "path": str(path),
        "exists": True,
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "mtime_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    }


def _sqlite_pragmas(db_path: Path) -> dict[str, Any]:
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()
        query_only = conn.execute("PRAGMA query_only").fetchone()
        return {
            "journal_mode": journal_mode[0] if journal_mode else None,
            "query_only": query_only[0] if query_only else None,
        }


def _table_row_counts(db_path: Path) -> dict[str, int | None]:
    counts: dict[str, int | None] = {}
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        for table in _MUTATION_WATCH_TABLES:
            if table in tables:
                counts[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            else:
                counts[table] = None
    return counts


def capture_db_snapshot(db_path: Path, *, label: str) -> dict[str, Any]:
    return {
        "label": label,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "db_path": str(db_path),
        "files": [_file_metadata(path) for path in _related_db_paths(db_path)],
        "pragmas": _sqlite_pragmas(db_path),
        "table_row_counts": _table_row_counts(db_path),
    }


def assert_no_mutation(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    before_files = {item["path"]: item for item in before["files"]}
    after_files = {item["path"]: item for item in after["files"]}
    for path, b in before_files.items():
        a = after_files.get(path)
        if not a:
            violations.append(f"missing file after smoke: {path}")
            continue
        if not b.get("exists"):
            continue
        if b.get("size_bytes") != a.get("size_bytes"):
            violations.append(
                f"size changed for {path}: {b.get('size_bytes')} -> {a.get('size_bytes')}"
            )
        if b.get("mtime_ns") != a.get("mtime_ns"):
            violations.append(
                f"mtime changed for {path}: {b.get('mtime_ns')} -> {a.get('mtime_ns')}"
            )
    before_counts = before.get("table_row_counts") or {}
    after_counts = after.get("table_row_counts") or {}
    for table, bcount in before_counts.items():
        acount = after_counts.get(table)
        if bcount is not None and acount is not None and bcount != acount:
            violations.append(f"row count changed for {table}: {bcount} -> {acount}")
    return violations


@dataclass
class GetOnlyClient:
    """Wrap FastAPI TestClient and hard-fail on any non-GET request."""

    _client: Any
    _attempted_methods: list[str]

    def get(self, url: str, **kwargs: Any) -> Any:
        self._attempted_methods.append("GET")
        return self._client.get(url, **kwargs)

    def __getattr__(self, name: str) -> Any:
        if name in {"post", "put", "patch", "delete", "options", "head"}:
            raise RuntimeError(f"GET-only smoke: attempted disallowed HTTP method {name.upper()}")
        return getattr(self._client, name)


def run_get_smoke(db_path: Path) -> dict[str, Any]:
    from fastapi.testclient import TestClient

    from hb_assistant.construction.analytics import create_app

    app = create_app(db_path=str(db_path))
    raw_client = TestClient(app)
    client = GetOnlyClient(raw_client, [])

    results: dict[str, Any] = {"requests": [], "http_methods_attempted": []}
    for filename, path, params in _GET_ENDPOINTS:
        started = time.perf_counter()
        if path.endswith("/export"):
            response = client.get(path, headers=_VIEWER_HEADERS, params=params or {})
            body: Any = response.text
            (EVIDENCE / filename).write_text(body, encoding="utf-8")
        else:
            response = client.get(path, headers=_VIEWER_HEADERS, params=params or {})
            body = response.json()
            (EVIDENCE / filename).write_text(json.dumps(body, indent=2), encoding="utf-8")
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        results["requests"].append(
            {
                "artifact": filename,
                "path": path,
                "params": params,
                "status_code": response.status_code,
                "elapsed_ms": elapsed_ms,
            }
        )
        if response.status_code != 200:
            raise RuntimeError(f"GET {path} failed: {response.status_code}")

    results["http_methods_attempted"] = list(client._attempted_methods)
    if any(method != "GET" for method in client._attempted_methods):
        raise RuntimeError("GET-only smoke violated: non-GET method recorded")
    return results


def run_redaction_qa() -> dict[str, Any]:
    from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks
    from hb_assistant.construction.analytics.project_schedule_narrative_qa import validate_rendered_text

    json_artifacts = [
        "18-live-dashboard-api.json",
        "19-live-dashboard-filter-missing.json",
        "20-live-dashboard-filter-stale.json",
        "21-live-dashboard-filter-needs-review.json",
        "22-live-dashboard-filter-operator-action.json",
    ]
    leaks_by_file: dict[str, list[str]] = {}
    for name in json_artifacts:
        payload = json.loads((EVIDENCE / name).read_text(encoding="utf-8"))
        leaks_by_file[name] = find_redaction_leaks(payload)

    export_md = (EVIDENCE / "23-live-portfolio-export.md").read_text(encoding="utf-8")
    language_qa = validate_rendered_text(export_md, surface="portfolio_export")
    forbidden_language = bool(_FORBIDDEN_LANGUAGE.search(export_md))
    export_leaks = find_redaction_leaks({"export": export_md})

    proof = {
        "json_redaction_leaks": leaks_by_file,
        "export_redaction_leaks": export_leaks,
        "export_language_qa": language_qa,
        "export_forbidden_language_detected": forbidden_language,
        "passed": (
            all(not leaks for leaks in leaks_by_file.values())
            and not export_leaks
            and language_qa.get("passed") is True
            and not forbidden_language
        ),
    }
    lines = [
        f"passed={proof['passed']}",
        "",
        "== JSON redaction leaks ==",
        json.dumps(leaks_by_file, indent=2),
        "",
        "== Export redaction leaks ==",
        json.dumps(export_leaks, indent=2),
        "",
        "== Export language QA ==",
        json.dumps(language_qa, indent=2),
        "",
        f"export_forbidden_language_detected={forbidden_language}",
    ]
    (EVIDENCE / "24-live-redaction-proof.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if not proof["passed"]:
        raise RuntimeError("Live redaction/language QA failed; see 24-live-redaction-proof.txt")
    return proof


def wait_http(url: str, timeout_s: int = 180) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status < 500:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(1)
    raise RuntimeError(f"not ready: {url}")


def capture_live_browser(db_path: Path) -> dict[str, Any]:
    overview = json.loads((EVIDENCE / "18-live-dashboard-api.json").read_text(encoding="utf-8"))
    expected_project_count = int((overview.get("portfolio_summary") or {}).get("project_count") or 0)
    if expected_project_count <= 0:
        raise RuntimeError("live overview project_count must be > 0 for browser proof")

    env = {
        **os.environ,
        "PYTHONPATH": f"{ROOT / 'src'}:{ROOT / 'subrepos/construction-financial-review/src'}",
        "PHASE18_EXPECTED_PROJECT_COUNT": str(expected_project_count),
        "PHASE18_SCREENSHOT_PATH": str(EVIDENCE / "25-live-browser-dashboard-overview.png"),
        "PHASE18_DASHBOARD_URL": f"http://127.0.0.1:{_VITE_PORT}/projects/all/schedule/review",
    }

    api_proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import uvicorn; "
                "from hb_assistant.construction.analytics import create_app; "
                f"app = create_app(db_path={str(db_path)!r}); "
                f"uvicorn.run(app, host='127.0.0.1', port={_API_PORT}, log_level='warning')"
            ),
        ],
        cwd=ROOT,
        env=env,
    )
    vite_proc = subprocess.Popen(
        [
            "npx",
            "vite",
            "--host",
            "127.0.0.1",
            "--port",
            str(_VITE_PORT),
            "--config",
            str(ROOT / "frontend" / "vite.phase18-live.config.ts"),
        ],
        cwd=ROOT / "frontend",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_http(f"http://127.0.0.1:{_API_PORT}/health")
        wait_http(f"http://127.0.0.1:{_VITE_PORT}/")
        result = subprocess.run(
            ["node", str(EVIDENCE / "capture_phase18_live_browser.cjs")],
            cwd=EVIDENCE,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        if result.returncode != 0:
            raise RuntimeError(f"live browser capture failed:\n{result.stdout}\n{result.stderr}")
        print(result.stdout)
        shot = EVIDENCE / "25-live-browser-dashboard-overview.png"
        if not shot.is_file() or shot.stat().st_size < 10_000:
            raise RuntimeError("live browser screenshot missing or too small")
        return {
            "screenshot": shot.name,
            "expected_project_count": expected_project_count,
            "stdout": result.stdout.strip(),
        }
    finally:
        vite_proc.terminate()
        api_proc.terminate()
        vite_proc.wait(timeout=15)
        api_proc.wait(timeout=15)


def write_smoke_notes(
    *,
    db_path: Path,
    before: dict[str, Any],
    after: dict[str, Any],
    mutation_violations: list[str],
    request_log: dict[str, Any],
    redaction: dict[str, Any],
    browser: dict[str, Any],
) -> None:
    overview = json.loads((EVIDENCE / "18-live-dashboard-api.json").read_text(encoding="utf-8"))
    summary = overview.get("portfolio_summary") or {}
    lines = [
        "# Phase 18 live DB GET-only smoke notes",
        "",
        f"- Captured at: {datetime.now(timezone.utc).isoformat()}",
        f"- Resolved DB: `{db_path}`",
        f"- HB_ASSISTANT_DB_PATH env: `{os.environ.get('HB_ASSISTANT_DB_PATH', '<unset>')}`",
        "- Mutation policy: GET-only; no POST/PATCH/import/recompute/sync",
        "",
        "## HTTP requests",
        "",
        json.dumps(request_log.get("requests") or [], indent=2),
        "",
        "## Portfolio summary (overview)",
        "",
        json.dumps(summary, indent=2),
        "",
        "## DB snapshot before",
        "",
        json.dumps(before, indent=2),
        "",
        "## DB snapshot after",
        "",
        json.dumps(after, indent=2),
        "",
        "## Mutation violations",
        "",
        json.dumps(mutation_violations, indent=2) if mutation_violations else "[]",
        "",
        "## Redaction QA",
        "",
        f"passed={redaction.get('passed')}",
        "",
        "## Live browser",
        "",
        json.dumps(browser, indent=2),
    ]
    (EVIDENCE / "26-live-smoke-notes.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    _setup_import_path()
    db_path = resolve_live_db_path()
    before = capture_db_snapshot(db_path, label="before")
    request_log = run_get_smoke(db_path)
    after = capture_db_snapshot(db_path, label="after")
    mutation_violations = assert_no_mutation(before, after)
    if mutation_violations:
        write_smoke_notes(
            db_path=db_path,
            before=before,
            after=after,
            mutation_violations=mutation_violations,
            request_log=request_log,
            redaction={"passed": False},
            browser={},
        )
        raise RuntimeError("Live DB mutation detected:\n" + "\n".join(mutation_violations))

    redaction = run_redaction_qa()
    browser = capture_live_browser(db_path)
    write_smoke_notes(
        db_path=db_path,
        before=before,
        after=after,
        mutation_violations=[],
        request_log=request_log,
        redaction=redaction,
        browser=browser,
    )
    print(json.dumps({"ok": True, "db_path": str(db_path), "browser": browser}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
