#!/usr/bin/env python3
"""S10 TWNU live schedule import, version diff, and cost-mapping workflow proof."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks  # noqa: E402

ZIP_PATH = Path("/Users/bobbyfetting/Downloads/schedule-xml-files.zip")
PROJECT_KEY = "tropical"
TWNU_FILES = (
    ("TWNU07.xml", 1177, 2658),
    ("TWNU16.xml", 1420, 3780),
    ("TWNU18.xml", 1378, 3718),
)


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def git_info() -> dict[str, str]:
    def _run(args: list[str]) -> str:
        cp = subprocess.run(args, cwd=REPO, capture_output=True, text=True, check=False)
        return (cp.stdout or "").strip()

    return {"branch": _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]), "commit_sha": _run(["git", "rev-parse", "HEAD"])}


def _client():
    from fastapi.testclient import TestClient

    from hb_assistant.construction.analytics import create_app
    from hb_assistant.config.path_policy import PathPolicy

    return TestClient(create_app(db_path=str(PathPolicy().get_db_path())))


def _headers() -> dict[str, str]:
    return {"X-HB-UI-Role": "operator"}


def import_file(client, filename: str, data: bytes) -> dict:
    preview = client.post(
        "/api/schedules/import-preview",
        headers=_headers(),
        files={"file": (filename, data, "application/xml")},
        data={"project_key": PROJECT_KEY},
    )
    if preview.status_code == 409:
        detail = preview.json().get("detail", {})
        if detail.get("code") == "duplicate_schedule_version":
            return {
                "filename": filename,
                "schedule_version_key": detail["schedule_version_key"],
                "activity_count": detail["activity_count"],
                "relationship_count": detail["relationship_count"],
                "duplicate": True,
            }
    if preview.status_code != 200:
        raise RuntimeError(f"preview failed for {filename}: {preview.status_code} {preview.text}")
    body = preview.json()
    if find_redaction_leaks(body):
        raise RuntimeError(f"preview redaction leak for {filename}")
    import_id = body["import_id"]
    commit = client.post(
        "/api/schedules/import-commit",
        headers=_headers(),
        json={"import_id": import_id, "project_key": PROJECT_KEY, "confirm": True},
    )
    if commit.status_code != 200:
        raise RuntimeError(f"commit failed for {filename}: {commit.status_code} {commit.text}")
    out = commit.json()
    if find_redaction_leaks(out):
        raise RuntimeError(f"commit redaction leak for {filename}")
    return {
        "filename": filename,
        "schedule_version_key": out["schedule_version_key"],
        "activity_count": body["activity_count"],
        "relationship_count": body["relationship_count"],
    }


def run_diff(client, from_v: str, to_v: str) -> dict:
    resp = client.get(
        f"/api/schedules/projects/{PROJECT_KEY}/diff",
        headers=_headers(),
        params={"from": from_v, "to": to_v},
    )
    if resp.status_code != 200:
        raise RuntimeError(f"diff failed {from_v} -> {to_v}: {resp.status_code}")
    body = resp.json()
    if find_redaction_leaks(body):
        raise RuntimeError("diff redaction leak")
    return body


def run_cost_mapping(client, schedule_version_key: str) -> dict:
    run = client.post(
        "/api/schedules/cost-mapping/runs",
        headers=_headers(),
        json={
            "project_key": PROJECT_KEY,
            "schedule_version_key": schedule_version_key,
            "operator_objective": "association_only",
        },
    )
    if run.status_code != 200:
        raise RuntimeError(f"cost mapping run failed: {run.status_code}")
    run_id = run.json()["mapping_run_id"]
    weight_before = client.get(f"/api/schedules/cost-weighting/{PROJECT_KEY}", headers=_headers())
    before_count = len(weight_before.json().get("weighting_results", []))

    cands = client.get(
        f"/api/schedules/cost-mapping/runs/{run_id}/candidates",
        headers=_headers(),
    ).json().get("candidates", [])
    for c in cands:
        client.post(
            f"/api/schedules/cost-mapping/candidates/{c['id']}/review",
            headers=_headers(),
            json={"operator_status": "approved"},
        )
    approve = client.post(
        f"/api/schedules/cost-mapping/runs/{run_id}/approve",
        headers=_headers(),
    )
    if approve.status_code != 200:
        raise RuntimeError(f"approve failed: {approve.status_code}")

    weight_after = client.get(f"/api/schedules/cost-weighting/{PROJECT_KEY}", headers=_headers())
    after_count = len(weight_after.json().get("weighting_results", []))
    return {
        "mapping_run_id": run_id,
        "weighting_before": before_count,
        "weighting_after": after_count,
        "candidates_reviewed": len(cands),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out-dir",
        default=str(REPO / "docs/evidence/schedule-intelligence-s10-twnu-workflow" / utc_stamp()),
    )
    parser.add_argument("--confirm", action="store_true", help="Write imports to live DB")
    args = parser.parse_args()
    out = Path(args.out_dir)

    if not args.confirm:
        print("Refusing live writes without --confirm", file=sys.stderr)
        return 2
    if not ZIP_PATH.exists():
        print(f"Missing zip: {ZIP_PATH}", file=sys.stderr)
        return 1

    client = _client()
    imports: list[dict] = []
    failures: list[str] = []

    with zipfile.ZipFile(ZIP_PATH) as zf:
        for filename, exp_acts, exp_rels in TWNU_FILES:
            try:
                data = zf.read(filename)
                rec = import_file(client, filename, data)
                if rec["activity_count"] != exp_acts:
                    failures.append(f"{filename} activity_count {rec['activity_count']} != {exp_acts}")
                if rec["relationship_count"] != exp_rels:
                    failures.append(f"{filename} relationship_count {rec['relationship_count']} != {exp_rels}")
                acts = client.get(
                    f"/api/schedules/versions/{rec['schedule_version_key']}/activities",
                    headers=_headers(),
                    params={"limit": 10000},
                )
                if acts.json().get("total_count") != exp_acts:
                    failures.append(f"{filename} persisted activity count mismatch")
                imports.append(rec)
            except RuntimeError as exc:
                failures.append(str(exc))

    diffs: list[dict] = []
    if len(imports) >= 2:
        keys = [i["schedule_version_key"] for i in imports]
        pairs = [(keys[0], keys[1]), (keys[1], keys[2]), (keys[0], keys[2])] if len(keys) >= 3 else [(keys[0], keys[1])]
        for from_v, to_v in pairs:
            try:
                diffs.append({"from": from_v, "to": to_v, "result": run_diff(client, from_v, to_v)})
            except RuntimeError as exc:
                failures.append(str(exc))

    mapping: dict | None = None
    if imports:
        try:
            mapping = run_cost_mapping(client, imports[-1]["schedule_version_key"])
            if mapping["weighting_before"] != 0 and mapping["weighting_after"] <= mapping["weighting_before"]:
                failures.append("weighting gate unexpected after TWNU18 mapping")
            if mapping["weighting_after"] < 1:
                failures.append("weighting empty after approved mapping on TWNU18")
        except RuntimeError as exc:
            failures.append(str(exc))

    proof = {
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "s10_twnu_workflow",
        **git_info(),
        "imports": imports,
        "diffs": diffs,
        "cost_mapping": mapping,
        "stop_condition_failures": failures,
        "status": "pass" if not failures else "fail",
    }
    write_json(out / "s10_twnu_workflow_proof.json", proof)
    readme = out / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# Schedule Intelligence S10 — TWNU Workflow",
                "",
                f"- status: **{proof['status']}**",
                f"- imports: {len(imports)}",
                f"- diffs: {len(diffs)}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())