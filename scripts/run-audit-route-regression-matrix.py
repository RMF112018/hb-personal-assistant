#!/usr/bin/env python3
"""Run the audit routing regression matrix offline or against a broker dispatch hook."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "subrepos" / "construction-financial-review" / "src"))
sys.path.insert(0, str(SCRIPTS))

from route_proof_lib import evaluate_route_expectations, route_actual  # noqa: E402
from hb_assistant.obsidian_mcp.prompt_preflight import route_prompt  # noqa: E402


def _offline_route(prompt: str, route_kwargs: dict[str, Any] | None = None) -> dict[str, Any]:
    return route_prompt(prompt, **(route_kwargs or {}))


def _broker_route(broker: Any) -> Callable[..., dict[str, Any]]:
    def route(prompt: str, route_kwargs: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = broker.dispatch("pa_prompt_route", {"prompt": prompt, **(route_kwargs or {})})
        if not payload.get("ok"):
            raise RuntimeError(payload.get("error") or payload.get("safe_message") or "route failed")
        return payload["result"]

    return route


def load_matrix_cases(path: Path) -> list[dict[str, Any]]:
    """Load case rows from a bare array or a versioned corpus wrapper."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("cases"), list):
        return payload["cases"]
    raise ValueError(f"unsupported matrix shape in {path}")


def run_matrix(
    cases: list[dict[str, Any]],
    route_fn: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    failures = 0
    for case in cases:
        prompt = case["prompt"]
        plan = route_fn(prompt, case.get("route_kwargs") or {})
        actual = route_actual(plan)
        mismatches = evaluate_route_expectations(case.get("expected") or {}, actual)
        ok = not mismatches
        if not ok:
            failures += 1
        rows.append(
            {
                "id": case.get("id"),
                "prompt": prompt,
                "pass": ok,
                "mismatches": mismatches,
                "actual": {
                    "workflow": actual.get("workflow"),
                    "next_step_tool": actual.get("next_step_tool"),
                    "currently_executable": actual.get("currently_executable"),
                    "execution_blocked_reason": actual.get("execution_blocked_reason"),
                    "operation_modality": actual.get("operation_modality"),
                    "arguments": actual.get("next_step_arguments"),
                },
            }
        )
    return {
        "pass": failures == 0,
        "pass_count": len(rows) - failures,
        "fail_count": failures,
        "total": len(rows),
        "cases": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--matrix",
        default=str(ROOT / "scripts" / "audit-route-regression-matrix.json"),
        help="Path to audit regression matrix JSON",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Write JSON report to this path (default: stdout only)",
    )
    parser.add_argument(
        "--broker",
        action="store_true",
        help="Route through NasMcpBroker on a fresh temp DB (closer to live MCP)",
    )
    parser.add_argument(
        "--from-env",
        action="store_true",
        help="Route through NasMcpBroker(NasMcpConfig.from_env()) — use inside live MCP container",
    )
    parser.add_argument(
        "--enforcement",
        default="",
        help="Filter versioned corpus cases by enforcement (e.g. required, accepted_partial)",
    )
    args = parser.parse_args()

    cases = load_matrix_cases(Path(args.matrix))
    if args.enforcement:
        cases = [c for c in cases if c.get("enforcement") == args.enforcement]
        if not cases:
            raise SystemExit(f"no cases matched enforcement={args.enforcement!r}")
    if args.from_env:
        from hb_assistant.nas_mcp.broker import NasMcpBroker
        from hb_assistant.nas_mcp.config import NasMcpConfig

        route_fn = _broker_route(NasMcpBroker(NasMcpConfig.from_env()))
        mode = "live_container_env"
    elif args.broker:
        import tempfile

        from hb_assistant.nas_mcp.broker import NasMcpBroker
        from hb_assistant.nas_mcp.config import NasMcpConfig, NasObsidianConfig, RootSpec
        from hb_assistant.store.migrator import SQLiteMigrator

        d = Path(tempfile.mkdtemp(prefix="audit-matrix-"))
        db = str(d / "db.sqlite")
        SQLiteMigrator(db_path=db).apply()
        vault = d / "vault"
        vault.mkdir()
        cfg = NasMcpConfig(
            db_path=Path(db),
            audit_dir=d / "audit",
            roots={"vault": RootSpec("vault", vault, "read_write")},
            obsidian=NasObsidianConfig(vault_root=vault, backup_dir=d / "bk", support_dir=d / "sup"),
        )
        route_fn = _broker_route(NasMcpBroker(cfg))
        mode = "broker_temp_db"
    else:
        route_fn = _offline_route
        mode = "offline_route_prompt"

    report = run_matrix(cases, route_fn)
    report["mode"] = mode
    report["matrix_path"] = args.matrix

    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())