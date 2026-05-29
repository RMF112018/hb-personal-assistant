"""Phase 05 Prompt 11 — Obsidian financial register tests (dry-run / apply / idempotent / no-raw)."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

import pytest

from hb_assistant.procore.financial_register import (
    apply_financial_register,
    build_financial_register,
)
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_commitment_projection import project_commitment_family
from hb_assistant.store.procore_owner_projection import project_owner_contract_family

_NOW = "2026-05-29T00:00:00Z"
_SINCE = "2026-04-29T00:00:00Z"


def _seeded_db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        db = Path(tf.name)
    SQLiteMigrator(db_path=str(db)).apply()
    project_owner_contract_family(
        "prime-contracts",
        {"id": 1, "number": "PC-1", "status": "Approved", "executed": False,
         "grand_total": "1000000.00", "title": "Prime contract pm@example.test",
         "currency_configuration": {"currency_iso_code": "USD"}},
        project_key="tropical", now_utc=_NOW, db_path=db,
    )
    project_commitment_family(
        "commitment-contracts",
        {"id": 2, "number": "SC-1", "status": "Pending", "executed": False,
         "grand_total": "500000.00", "vendor": {"id": 12, "name": "Acme LLC"}},
        project_key="tropical", now_utc=_NOW, db_path=db,
    )
    return db


def test_build_has_ten_sections_and_record_keys() -> None:
    db = _seeded_db()
    result = build_financial_register("tropical", now_utc=_NOW, since_utc=_SINCE, db_path=db)
    assert len(result["sections"]) == 10
    assert result["counts"]["contracts"] == 2
    # pipes inside a record_key are markdown-escaped (\|) in table cells; unescape to compare
    rendered = result["rendered"]
    unescaped = rendered.replace("\\|", "|")
    # every populated row carries its source record_key
    assert "tropical|prime-contracts||1" in unescaped
    assert "tropical|commitment-contracts||2" in unescaped
    # each section embeds a local query reference
    assert "_Query: `hb-assistant procore live financial" in rendered
    assert rendered.count("## ") >= 10  # 10 sections (+ Guardrails)


def test_build_emits_no_raw_sensitive() -> None:
    db = _seeded_db()
    rendered = build_financial_register(
        "tropical", now_utc=_NOW, since_utc=_SINCE, db_path=db
    )["rendered"]
    for pat in (r"https?://", r"[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}", r"Bearer\s+[A-Za-z0-9]",
                r"-----BEGIN", r"sig="):
        assert re.search(pat, rendered) is None, f"leaked {pat!r}"
    assert "pm@example.test" not in rendered  # contract title email masked upstream


def test_apply_writes_marker_bounded_file_and_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = tmp_path / "construction-vault"
    vault.mkdir()
    monkeypatch.setenv("HB_CONSTRUCTION_VAULT_ROOT", str(vault))
    db = _seeded_db()

    first = apply_financial_register("tropical", now_utc=_NOW, since_utc=_SINCE, db_path=db)
    assert first["vault_configured"] is True
    assert len(first["written_paths"]) == 1
    written = Path(first["written_paths"][0])
    assert written.name == "tropical.procore-financial-register.md"
    assert written.parent == vault / "01_Projects"
    blob = written.read_text(encoding="utf-8")
    assert "<!-- HB-PROCORE-FINANCIAL-REGISTER:START -->" in blob
    assert "<!-- HB-PROCORE-FINANCIAL-REGISTER:END -->" in blob
    assert "Contract Summary" in blob and "Retainage / Payment Risk" in blob

    first_bytes = written.read_bytes()
    apply_financial_register("tropical", now_utc=_NOW, since_utc=_SINCE, db_path=db)
    assert written.read_bytes() == first_bytes, "register apply must be byte-identical on rerun"


def test_dry_run_writes_no_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault = tmp_path / "construction-vault"
    vault.mkdir()
    monkeypatch.setenv("HB_CONSTRUCTION_VAULT_ROOT", str(vault))
    db = _seeded_db()
    # build (dry-run equivalent) must not write anything to 01_Projects
    build_financial_register("tropical", now_utc=_NOW, since_utc=_SINCE, db_path=db)
    assert not (vault / "01_Projects").exists()
