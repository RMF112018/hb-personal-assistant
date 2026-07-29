from hb_assistant.cli.apple_mcc import main
from hb_assistant.apple_mcc.importer.cli import main as importer_main

def test_cli_dry_runs():
    assert main(["dry-run", "--action", "status"]) == 0
    assert importer_main(["--dry-run"]) == 0
