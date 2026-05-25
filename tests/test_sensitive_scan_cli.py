from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.main import app


runner = CliRunner()


def test_scan_sensitive_cli_structured_output(tmp_path: Path) -> None:
    app_support = tmp_path / "app-support"
    app_support.mkdir(parents=True, exist_ok=True)
    cfg = tmp_path / "cfg.yml"
    cfg.write_text(
        f"paths:\n  application_support_root: '{app_support}'\n",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text("CLIENT_SECRET=abc\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["diagnostics", "scan-sensitive", "--repo", str(tmp_path), "--json"],
        env={"HB_PA_CONFIG": str(cfg)},
    )
    assert result.exit_code == 0
    assert '"findings"' in result.stdout
    assert '"findings_by_category"' in result.stdout
    assert '"category"' in result.stdout
    assert '"line"' in result.stdout
    assert '"severity"' in result.stdout
