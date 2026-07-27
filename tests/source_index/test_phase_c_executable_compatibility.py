"""PC-WI-04 Stage-3 — executable / database compatibility and rollback (PC-AC-040..042, PCR-007).

Runs a **prior executable** (pinned historical SHA `6b57a406`, head V124) from a ``git worktree`` and
performs bounded DAO reads against representative databases, so the compatibility classification is
produced by real historical execution — never static inspection relabeled as a compatibility proof:

- PC-AC-041 — the prior executable performs bounded DAO reads against a **prior-restored V124 database**
  (the §8 rollback combination: restore + prior executable) → rollback combination proven.
- PC-AC-040 — the prior executable run against a **new V127 database** is classified: it opens and reads
  the newer additive database at the DB-access layer (does not fail-closed on the higher head) and reads
  a V124-known source-index table, but cannot use V125+ features.
- PC-AC-042 — the governing spec (§8) and the compatibility note state that in-place schema downgrade is
  unsupported unless separately implemented (rollback = restore + prior executable).

Fail-closed (PCR-007): if the pinned prior-executable SHA cannot be checked out — i.e. historical
execution cannot be reproduced — the compatibility tests fail with an INSUFFICIENT-EVIDENCE message
rather than passing.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

import tests.support.source_index_compat_probe as compat_probe
from hb_assistant.store.sqlite_backup import backup_database, restore_backup
from tests.support.source_index_migration_fixture import build_fixture

_PRIOR_EXEC_SHA = "6b57a406"  # head V124 ("perf(source-index): index the FTS-search join key (V124)")
_PRIOR_EXEC_LATEST = 124
_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROBE = Path(compat_probe.__file__)
_SUBPROCESS_PYTHONPATH_SUFFIX = "subrepos/construction-financial-review/src"
_COMPAT_DOC = _REPO_ROOT / "docs/architecture/source-index-phase-c-executable-compatibility.md"
_SPEC = _REPO_ROOT / "docs/specs/source-index-phase-c-migration-rollback-proof.md"


@pytest.fixture(scope="module")  # type: ignore[untyped-decorator]  # pytest.fixture is untyped under mypy --strict
def prior_exec_worktree(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """Check out the pinned prior executable in a git worktree (removed on teardown). Fail-closed to an
    INSUFFICIENT-EVIDENCE error if the historical SHA cannot be reproduced (PCR-007)."""
    wt = tmp_path_factory.mktemp("prior_exec") / "v124"
    add = subprocess.run(
        ["git", "-C", str(_REPO_ROOT), "worktree", "add", "--detach", str(wt), _PRIOR_EXEC_SHA],
        capture_output=True,
        text=True,
    )
    if add.returncode != 0:
        pytest.fail(
            "INSUFFICIENT EVIDENCE — could not check out prior-executable SHA "
            f"{_PRIOR_EXEC_SHA}; historical execution not reproduced: {add.stderr.strip()}"
        )
    try:
        yield wt
    finally:
        subprocess.run(
            ["git", "-C", str(_REPO_ROOT), "worktree", "remove", "--force", str(wt)],
            capture_output=True,
            text=True,
        )


def _run_prior_probe(worktree: Path, db: Path, out: Path) -> dict[str, object]:
    """Run the bounded-DAO-read probe under the prior executable (worktree code) and return its JSON."""
    env_pythonpath = f"{worktree / 'src'}:{_SUBPROCESS_PYTHONPATH_SUFFIX}"
    proc = subprocess.run(
        [sys.executable, str(_PROBE), "--db", str(db), "--out", str(out)],
        cwd=str(_REPO_ROOT),
        env={"PYTHONPATH": env_pythonpath, "PATH": _env_path()},
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"prior-executable probe failed: {proc.stderr.strip()}"
    return json.loads(out.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _env_path() -> str:
    import os

    return os.environ.get("PATH", "")


def _as_str_list(value: object) -> list[str]:
    assert isinstance(value, list) and all(isinstance(v, str) for v in value), value
    return value


def test_prior_executable_reads_prior_restored_database(  # PC-AC-041
    prior_exec_worktree: Path, tmp_path: Path
) -> None:
    root = tmp_path / "rehearsal"
    root.mkdir()
    fx = build_fixture(root, _PRIOR_EXEC_LATEST, row_count=6, filename="origin_v124.sqlite")

    # §8 rollback combination: restore the prior backup to a NEW path, then run the prior executable.
    dest = root / "backups"
    dest.mkdir()
    result = backup_database(fx.db_path, dest, rehearsal_root=root)
    restore_dir = root / "restored"
    restore_dir.mkdir()
    restored = restore_backup(result.backup_path, restore_dir / "restored_v124.sqlite", rehearsal_root=root)

    probe = _run_prior_probe(prior_exec_worktree, restored, tmp_path / "probe_v124.json")
    assert probe["prior_latest_schema_version"] == _PRIOR_EXEC_LATEST  # genuinely the prior executable
    assert probe["read_ok"] is True, probe["error"]
    assert probe["current_version_read"] == _PRIOR_EXEC_LATEST  # prior exec sees its own head
    # genuine prior repository DAO operation against the prior-restored database
    counts = probe["repo_generated_note_counts"]
    assert isinstance(counts, dict) and "generated_card_count" in counts
    # its own database carries only event types it knows — nothing unrecognized
    assert probe["unknown_event_types"] == []


def test_old_executable_new_database_reads_generation_path_only_not_moved_queue(  # PC-AC-040
    prior_exec_worktree: Path, tmp_path: Path
) -> None:
    root = tmp_path / "rehearsal"
    root.mkdir()
    fx = build_fixture(root, 127, row_count=6, filename="new_v127.sqlite")

    probe = _run_prior_probe(prior_exec_worktree, fx.db_path, tmp_path / "probe_v127.json")
    assert probe["prior_latest_schema_version"] == _PRIOR_EXEC_LATEST  # it IS the old (V124) executable

    # NARROW classification: the ONLY forward-read compatibility proven is the read-only generation-table
    # path — the prior executable's repository DAO still returns generation counts against a V127 database.
    assert probe["read_ok"] is True, probe["error"]
    assert probe["current_version_read"] == 127
    counts = probe["repo_generated_note_counts"]
    assert isinstance(counts, dict) and "generated_card_count" in counts

    # NOT general forward compatibility: V127 rebuilds source_intelligence_events and adds the governed
    # 'moved' event type, which the prior V124 executable has no knowledge of. It therefore cannot safely
    # process the event queue against a V127 database.
    known = _as_str_list(probe["known_event_types"])
    present = _as_str_list(probe["present_event_types"])
    unknown = _as_str_list(probe["unknown_event_types"])
    assert "moved" not in known  # prior executable does not understand 'moved'
    assert "moved" in present  # but the V127 database contains a 'moved' event
    assert "moved" in unknown  # -> an event the prior executable cannot interpret


def test_prior_executable_cannot_interpret_v127_moved_event(  # PC-AC-040 (semantic coverage)
    prior_exec_worktree: Path, tmp_path: Path
) -> None:
    root = tmp_path / "rehearsal"
    root.mkdir()
    fx = build_fixture(root, 127, row_count=6, filename="moved_probe_v127.sqlite")

    probe = _run_prior_probe(prior_exec_worktree, fx.db_path, tmp_path / "probe_moved.json")
    assert probe["read_ok"] is True, probe["error"]
    # The prior V124 executable's known event-type vocabulary excludes 'moved'; a V127 database presents a
    # 'moved' row it would misclassify. This proves the classification is read-only generation-path only,
    # never safe queue processing or write operation under the prior executable against V127.
    assert probe["known_event_types"] == ["created", "deleted", "modified", "rebuild", "reindex_requested"]
    assert "moved" in _as_str_list(probe["unknown_event_types"])


def test_schema_downgrade_is_documented_unsupported() -> None:  # PC-AC-042
    assert _SPEC.is_file() and _COMPAT_DOC.is_file()
    spec = _SPEC.read_text(encoding="utf-8").lower()
    doc = _COMPAT_DOC.read_text(encoding="utf-8").lower()
    # Governing spec §8 and the compatibility note both state downgrade is unsupported.
    assert "schema downgrade is unsupported" in spec
    assert "schema downgrade is unsupported" in doc
    assert "restore + prior executable" in doc  # rollback contract stated, not an in-place downgrade
