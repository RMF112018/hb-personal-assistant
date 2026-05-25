from __future__ import annotations

from pathlib import Path

from hb_assistant.security import ScanConfig, SensitiveScanner


def _write_cfg(tmp_path: Path) -> Path:
    app_support = tmp_path / "app-support"
    app_support.mkdir(parents=True, exist_ok=True)
    cfg = tmp_path / "cfg.yml"
    cfg.write_text(
        f"paths:\n  application_support_root: '{app_support}'\n",
        encoding="utf-8",
    )
    return cfg


def test_sensitive_scan_detects_synthetic_token_without_leaking_value(tmp_path: Path, monkeypatch) -> None:
    cfg = _write_cfg(tmp_path)
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))

    target = tmp_path / "sample.env"
    target.write_text("CLIENT_SECRET=super-secret-value\n", encoding="utf-8")

    scanner = SensitiveScanner(ScanConfig(max_file_size_bytes=100_000, max_lines_per_file=100, max_files=200))
    payload = scanner.scan(repo=str(tmp_path))

    assert payload["implemented"] is True
    assert any(f["category"] == "client_secret_assignment" for f in payload["findings"])
    out = str(payload)
    assert "super-secret-value" not in out


def test_sensitive_scan_false_positive_handling(tmp_path: Path, monkeypatch) -> None:
    cfg = _write_cfg(tmp_path)
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))

    target = tmp_path / "notes.txt"
    target.write_text("this document discusses tokens conceptually only\n", encoding="utf-8")

    scanner = SensitiveScanner()
    payload = scanner.scan(repo=str(tmp_path))
    assert payload["findings"] == []


def test_sensitive_scan_skips_binary(tmp_path: Path, monkeypatch) -> None:
    cfg = _write_cfg(tmp_path)
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))

    target = tmp_path / "bin.dat"
    target.write_bytes(b"\x00\x01\x02\x03\x04")

    scanner = SensitiveScanner()
    payload = scanner.scan(repo=str(tmp_path))
    assert payload["stats"]["files_binary_skipped"] >= 1


def test_sensitive_scan_oversize_skip_and_high_risk_override(tmp_path: Path, monkeypatch) -> None:
    cfg = _write_cfg(tmp_path)
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))

    big_txt = tmp_path / "big.txt"
    big_txt.write_text("A" * 700_000, encoding="utf-8")

    big_env = tmp_path / ".env"
    big_env.write_text("API_KEY=abcdef1234567890\n" + ("X" * 700_000), encoding="utf-8")

    scanner = SensitiveScanner(ScanConfig(max_file_size_bytes=100_000, max_lines_per_file=200, max_files=300))
    payload = scanner.scan(repo=str(tmp_path))

    assert payload["stats"]["files_oversize_skipped"] >= 1
    assert any(f["category"] == "env_secret_assignment" for f in payload["findings"])
