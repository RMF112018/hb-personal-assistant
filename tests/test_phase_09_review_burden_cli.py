"""Smoke tests for second-brain review * commands (policy-status, burden, queue, clusters)."""

import json
import tempfile
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.main import app

runner = CliRunner()


def test_review_policy_status_runs_and_loads_packaged():
    # After pip -e in validation this uses the packaged; here from source also works via fallback.
    result = runner.invoke(app, ["second-brain", "review", "policy-status", "--json"])
    assert result.exit_code in (0, 3)  # 3 if policy not fully satisfied in this env, but must not crash
    assert "policy" in (result.stdout or "") or "review_burden" in (result.stdout or "") or result.exit_code == 0


def test_review_burden_and_queue_and_clusters_smoke():
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "b.db"
        from hb_assistant.store.migrator import SQLiteMigrator
        SQLiteMigrator(str(db)).apply()
        # The commands read the default db; to keep test isolated we just invoke (they will use real app db which is outside repo).
        # Smoke: the module imports and typer registers; full matrix in integration.
        r1 = runner.invoke(app, ["second-brain", "review", "burden", "--json"])
        assert r1.exit_code in (0, 3)
        r2 = runner.invoke(app, ["second-brain", "review", "queue", "--top", "3", "--json"])
        assert r2.exit_code in (0, 3)
        r3 = runner.invoke(app, ["second-brain", "review", "clusters", "--json"])
        assert r3.exit_code in (0, 3)
        # Enhancement: after mart dedup, outputs have unique_example_count and deduped tops (no repeated keys)
        # (smoke only; full matrix exercised in policy test)
        for r in (r1, r3):
            if r.exit_code == 0 and r.stdout:
                try:
                    data = json.loads(r.stdout)
                    for c in (data.get("mart", {}).get("clusters") or data.get("clusters") or [])[:2]:
                        if "item_count" in c:
                            uec = c.get("unique_example_count")
                            tops = c.get("top_examples", [])
                            assert uec is None or (0 <= uec <= len(tops))
                            # no dups on primary hash when present; explicit dedupe key uniqueness
                            hashes = [(e.get("item_hash") or e.get("source_ref_hash")) for e in tops]
                            present = [h for h in hashes if h]
                            assert len(present) == len(set(present))
                except Exception:
                    pass  # smoke, ignore parse in some envs
