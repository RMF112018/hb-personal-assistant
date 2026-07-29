#!/usr/bin/env python3
"""Integrated pre-merge green orchestrator for Apple MCC candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from schemas import PredicateFail, SchemaError, validate


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ev", required=True)
    p.add_argument("--candidate", default="")
    p.add_argument("--skip-gates", action="store_true", help="Skip ruff/mypy/pytest gates (dev only)")
    p.add_argument("--blocks-merge-ac-json", default="[]")
    args = p.parse_args(argv)

    ev = Path(args.ev)
    cand = args.candidate or subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    failures: list[str] = []

    # 1. reg receipt
    reg = ev / "reg-receipt.json"
    if not reg.is_file():
        failures.append("missing_reg_receipt")
    else:
        try:
            validate("reg_receipt", _read_json(reg))
        except (SchemaError, PredicateFail) as exc:
            failures.append(f"reg_receipt:{exc}")

    # 2. wp00..wp11 receipts
    for nn in [f"{i:02d}" for i in range(0, 12)]:
        path = ev / f"wp{nn}-receipt.json"
        if not path.is_file():
            failures.append(f"missing_wp_receipt:{nn}")
            continue
        try:
            validate("wp_receipt", _read_json(path))
        except (SchemaError, PredicateFail) as exc:
            failures.append(f"wp_receipt:{nn}:{exc}")

    # 3. blocks_merge AC exits
    ac_ids = json.loads(args.blocks_merge_ac_json)
    for ac_id in ac_ids:
        exit_path = ev / "ac" / f"{ac_id}.exit"
        log_path = ev / "ac" / f"{ac_id}.log"
        if not exit_path.is_file():
            failures.append(f"missing_ac_exit:{ac_id}")
            continue
        code = exit_path.read_text(encoding="utf-8").strip()
        if code != "0":
            failures.append(f"ac_exit_nonzero:{ac_id}:{code}")
        if log_path.is_file():
            last = log_path.read_text(encoding="utf-8").strip().splitlines()[-1]
            if "AC_RESULT=PASS" not in last:
                failures.append(f"ac_result_not_pass:{ac_id}")

    cand_dir = ev / "candidate" / cand
    # 4. gate exits when present
    if not args.skip_gates:
        for gate in ("test-safe", "ruff", "mypy"):
            exit_path = cand_dir / f"{gate}.exit"
            if exit_path.is_file() and exit_path.read_text(encoding="utf-8").strip() != "0":
                failures.append(f"gate_fail:{gate}")

    # 5. env-identity / collected-nodes hashes
    for name in ("env-identity.json", "env-identity.sha256", "collected-nodes.txt", "collected-nodes.sha256"):
        if not (cand_dir / name).is_file():
            failures.append(f"missing:{name}")
    if (cand_dir / "env-identity.json").is_file() and (cand_dir / "env-identity.sha256").is_file():
        expected = (cand_dir / "env-identity.sha256").read_text(encoding="utf-8").strip()
        if _sha(cand_dir / "env-identity.json") != expected:
            failures.append("env_identity_hash_mismatch")
    if (cand_dir / "collected-nodes.txt").is_file() and (cand_dir / "collected-nodes.sha256").is_file():
        expected = (cand_dir / "collected-nodes.sha256").read_text(encoding="utf-8").strip()
        if _sha(cand_dir / "collected-nodes.txt") != expected:
            failures.append("collected_nodes_hash_mismatch")

    # 6. tf-validate
    tfv = cand_dir / "tf-validate.json"
    if tfv.is_file():
        try:
            validate("tf_validate_result", _read_json(tfv))
        except (SchemaError, PredicateFail) as exc:
            failures.append(f"tf_validate:{exc}")
    else:
        failures.append("missing_tf_validate")

    # 7. candidate-evidence-index (non-self-referential)
    idx = cand_dir / "candidate-evidence-index.json"
    idx_sha = cand_dir / "index.sha256"
    if not idx.is_file():
        failures.append("missing_candidate_evidence_index")
    else:
        try:
            validate("candidate_evidence_index", _read_json(idx))
        except (SchemaError, PredicateFail) as exc:
            failures.append(f"candidate_index:{exc}")
        if idx_sha.is_file():
            if _sha(idx) != idx_sha.read_text(encoding="utf-8").strip():
                failures.append("index_sha_mismatch")
        else:
            failures.append("missing_index_sha256_sidecar")

    report = {
        "candidate_sha": cand,
        "failures": failures,
        "ok": not failures,
        "produced_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out = cand_dir / "integrated-green-report.json"
    cand_dir.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if failures:
        print("INTEGRATED_GREEN_FAIL", *failures, sep="\n")
        return 1
    print(f"INTEGRATED_GREEN_OK {cand}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
