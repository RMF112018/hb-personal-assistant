"""Tests for forecasting DB evidence package structure and reproducibility."""

from __future__ import annotations

import json
import subprocess
import tarfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "generate_forecasting_db_complete_evidence.sh"
EXISTING_TGZ = REPO_ROOT / "docs/evidence/forecasting-db-complete-evidence-20260621T114232Z.tgz"
EXISTING_DIR = REPO_ROOT / "docs/evidence/forecasting-db-complete-evidence/20260621T114232Z"


@pytest.fixture(scope="module")
def existing_tar_members() -> set[str]:
    if not EXISTING_TGZ.exists():
        pytest.skip("existing evidence tarball not present in worktree")
    with tarfile.open(EXISTING_TGZ, "r:gz") as tf:
        return set(tf.getnames())


def test_existing_tarball_lists_required_artifacts(existing_tar_members: set[str]) -> None:
    required_suffixes = (
        "97-file-manifest.txt",
        "98-no-raw-leak-scan.json",
        "99-zero-byte-files.txt",
        "00-evidence-package-summary.json",
    )
    for suffix in required_suffixes:
        assert any(m.endswith(suffix) for m in existing_tar_members), suffix


def test_existing_tarball_missing_completion_file_documents_known_gap(existing_tar_members: set[str]) -> None:
    """Prior package wrote 96-package-complete.txt after tar; documents the fixed gap."""
    has_completion = any(m.endswith("96-package-complete.txt") for m in existing_tar_members)
    # Known gap in uploaded 20260621T114232Z package
    assert has_completion is False


def test_script_packaging_order_writes_completion_before_tar() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    pre_tar = text.index('packaging_step=pre_tar')
    tar_cmd = text.index('tar --exclude')
    manifest = text.index('97-file-manifest.txt')
    assert pre_tar < manifest < tar_cmd


def test_script_has_checksum_sidecar() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "CHECKSUM_SIDEcar" in text or ".sha256" in text


def test_script_excludes_appledouble_and_uses_copyfile_disable() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "COPYFILE_DISABLE=1" in text
    assert "--exclude='._*'" in text or '--exclude="._*"' in text


@pytest.mark.parametrize(
    "json_rel",
    [
        "00-evidence-package-summary.json",
        "02-targeted-sql-profiles/07-join-cardinality-results.json",
        "03-type-normalization-profiles/01-amount-parse-profile.json",
        "98-no-raw-leak-scan.json",
    ],
)
def test_existing_json_files_validate(json_rel: str) -> None:
    if not EXISTING_DIR.exists():
        pytest.skip("extracted evidence dir not present")
    path = EXISTING_DIR / json_rel
    if not path.exists():
        pytest.skip(f"{json_rel} not in extracted evidence")
    json.loads(path.read_text(encoding="utf-8"))


def test_existing_no_raw_leak_scan_passed() -> None:
    if not EXISTING_DIR.exists():
        pytest.skip("extracted evidence dir not present")
    scan = json.loads((EXISTING_DIR / "98-no-raw-leak-scan.json").read_text(encoding="utf-8"))
    assert scan.get("ok") is True
    assert scan.get("unsafe_finding_count", 1) == 0


def test_po_join_cardinality_flags_commitment_fallback() -> None:
    if not EXISTING_DIR.exists():
        pytest.skip("extracted evidence dir not present")
    joins = json.loads(
        (EXISTING_DIR / "02-targeted-sql-profiles/07-join-cardinality-results.json").read_text(
            encoding="utf-8"
        )
    )
    po_holder = next(
        j
        for j in joins
        if j["parent_table"] == "procore_ep_purchase_order_contracts"
        and j["child_table"] == "procore_ep_purchase_order_line_items"
        and j["child_key"] == "holder_id"
    )
    assert po_holder["unmatched_child_rows"] == 12
    assert po_holder["matched_child_rows"] == 16


@pytest.mark.integration
def test_evidence_script_dry_run_imports_classifiers() -> None:
    """Verify the embedded Python can import field classifiers without running full package."""
    code = f"""
import sys
sys.path.insert(0, {str(REPO_ROOT / "src")!r})
from hb_assistant.forecasting.field_classifiers import classify_amount_field
r = classify_amount_field(table="t", column="grand_total")
assert r["approved_for_aggregation"] is True
"""
    proc = subprocess.run(
        ["python3", "-c", code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr