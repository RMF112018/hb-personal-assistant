"""A3 — canonical structure-root mapping authority (Phase A).

One shared exact/explicit resolver (`source_root_mapping.resolve_structure_mapping`) is the sole
authority for file-index-root -> structure-index-root resolution, used by health, bootstrap, and watcher
readiness. No fuzzy substring / prefix / first-row fallback. Deterministic precedence:
    validated one-operation CLI override -> configured structure_root_map -> exact normalized key -> unmapped
An ephemeral CLI override must not certify durable watcher readiness unless it matches canonical config.

Unit tests lazy-import the resolver so the file still collects against the pre-A3 parent (where the module
is absent) and the health fuzzy-defect test can demonstrate the behavioral regression it removes.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from hb_assistant.config.loader import load_config as load_app_config
from hb_assistant.obsidian_mcp import source_bootstrap as sb
from hb_assistant.obsidian_mcp.config import ExternalSourceRoot, ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_health_service import source_index_health
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_structure_classifier import classify_root
from hb_assistant.obsidian_mcp.source_structure_repository import SourceStructureRepository
from hb_assistant.store.migrator import SQLiteMigrator

# Adversarial collision corpus (audit A3): keys that fuzzy substring/prefix matching would cross-map.
CORPUS = [
    "work",
    "syn-work",
    "work-backup",
    "backup-work",
    "home",
    "home-work",
    "vault",
    "vault-backup",
    "project",
    "projects",
]

_TEMPLATE_DB: str | None = None


def _template_db() -> str:
    global _TEMPLATE_DB
    if _TEMPLATE_DB is None:
        import tempfile

        p = str(Path(tempfile.mkdtemp(prefix="a3tmpl_")) / "t.db")
        SQLiteMigrator(db_path=p).apply()
        _TEMPLATE_DB = p
    return _TEMPLATE_DB


def _seed_structure_root(db: str, root_key: str, folder_count: int = 5) -> None:
    srepo = SourceStructureRepository(db)
    root = classify_root(root_key, root_key)
    root.folder_count = folder_count
    root.file_count = folder_count * 2
    root.last_indexed_at = "2026-01-01T00:00:00+00:00"
    srepo.upsert_root(root)


# ==================================================================================================
# resolver unit tests (adversarial corpus, precedence, provenance, invalid/ambiguous, normalization)
# ==================================================================================================
def test_exact_normalized_key_match_succeeds():
    from hb_assistant.obsidian_mcp import source_root_mapping as srm

    m = srm.resolve_structure_mapping("work", ["work"])
    assert m.structure_key == "work"
    assert m.reason == "exact_match"


def test_configured_explicit_map_succeeds_with_provenance():
    from hb_assistant.obsidian_mcp import source_root_mapping as srm

    m = srm.resolve_structure_mapping("syn-work", ["work"], config_map={"syn-work": "work"})
    assert m.structure_key == "work"
    assert m.reason == "explicit_map"


def test_invalid_explicit_map_target_fails_closed():
    from hb_assistant.obsidian_mcp import source_root_mapping as srm

    m = srm.resolve_structure_mapping("work", ["work"], config_map={"work": "does-not-exist"})
    assert m.structure_key is None
    assert m.reason == "invalid_explicit_map"


def test_work_does_not_match_syn_work():
    from hb_assistant.obsidian_mcp import source_root_mapping as srm

    assert srm.resolve_structure_mapping("work", ["syn-work"]).structure_key is None
    assert srm.resolve_structure_mapping("work", ["syn-work"]).reason == "unmapped"


def test_work_does_not_match_work_backup():
    from hb_assistant.obsidian_mcp import source_root_mapping as srm

    assert srm.resolve_structure_mapping("work", ["work-backup"]).structure_key is None


def test_home_does_not_match_home_work():
    from hb_assistant.obsidian_mcp import source_root_mapping as srm

    assert srm.resolve_structure_mapping("home", ["home-work"]).structure_key is None


def test_full_corpus_no_cross_collision_without_explicit_map():
    from hb_assistant.obsidian_mcp import source_root_mapping as srm

    # Each key resolves to ITSELF or to nothing — never to a different corpus key via substring.
    for key in CORPUS:
        m = srm.resolve_structure_mapping(key, CORPUS)
        assert m.structure_key == key and m.reason == "exact_match"
        # against a namespace that excludes the exact key, it must be unmapped (never a fuzzy neighbor)
        others = [k for k in CORPUS if k != key]
        m2 = srm.resolve_structure_mapping(key, others)
        assert m2.structure_key is None and m2.reason == "unmapped"


def test_cli_override_precedence_and_provenance():
    from hb_assistant.obsidian_mcp import source_root_mapping as srm

    m = srm.resolve_structure_mapping(
        "work",
        ["project", "projects"],
        config_map={"work": "project"},
        cli_override={"work": "projects"},
    )
    assert m.structure_key == "projects"
    assert m.reason == "cli_override"


def test_many_to_one_mapping_allowed():
    from hb_assistant.obsidian_mcp import source_root_mapping as srm

    cfg = {"syn-work": "work", "work-backup": "work"}
    assert (
        srm.resolve_structure_mapping("syn-work", ["work"], config_map=cfg).structure_key == "work"
    )
    assert (
        srm.resolve_structure_mapping("work-backup", ["work"], config_map=cfg).structure_key
        == "work"
    )


def test_duplicate_source_keys_after_normalization_rejected():
    from hb_assistant.obsidian_mcp import source_root_mapping as srm

    # "work" and "work " normalize to the same source key with DIFFERENT targets -> ambiguous, fail closed.
    m = srm.resolve_structure_mapping("work", ["a", "b"], config_map={"work": "a", "work ": "b"})
    assert m.structure_key is None
    assert m.reason == "ambiguous_configuration"


def test_normalizer_is_shared_and_deterministic():
    from hb_assistant.obsidian_mcp import source_root_mapping as srm

    assert srm.normalize_root_key("  work ") == "work"
    assert srm.normalize_root_key("work") == srm.normalize_root_key(" work")
    # exact match tolerates surrounding whitespace via the shared normalizer
    assert srm.resolve_structure_mapping(" work ", ["work"]).structure_key == "work"


def test_resolver_never_raises_on_degenerate_inputs():
    from hb_assistant.obsidian_mcp import source_root_mapping as srm

    assert srm.resolve_structure_mapping("work", []).structure_key is None
    assert srm.resolve_structure_mapping("", ["work"]).structure_key is None


def test_bootstrap_wrapper_delegates_to_shared_resolver():
    # The legacy resolve_structure_key wrapper preserves behavior AND is backed by the shared resolver.
    assert sb.resolve_structure_key("k", {"k": "/x"}) == "k"
    assert sb.resolve_structure_key("fileK", {"structK": "/x"}, {"fileK": "structK"}) == "structK"
    assert sb.resolve_structure_key("work", {"work-backup": "/x"}) is None  # no fuzzy


# ==================================================================================================
# integration: health removes fuzzy + equals bootstrap/watcher; durability; no path leak
# ==================================================================================================
def _env(tmp_path: Path, *, file_key: str, structure_key: str, watch: bool = True):
    db = str(tmp_path / "h.db")
    shutil.copy(_template_db(), db)
    root = tmp_path / "root"
    root.mkdir(exist_ok=True)
    (root / "a.md").write_text("alpha", encoding="utf-8")
    ocfg = ObsidianMcpConfig(
        external_sources=[ExternalSourceRoot(source_root_key=file_key, path=str(root))],
        external_source_index_enabled=True,
        external_source_watch_enabled=watch,
    )
    acfg = load_app_config()
    acfg.source_structure.scan_roots = {structure_key: str(root)}
    _seed_structure_root(db, structure_key)
    return db, root, ocfg, acfg


def test_health_does_not_fuzzy_match_work_to_work_backup(tmp_path):
    # file root "work"; only a "work-backup" structure root exists. Fuzzy matching (pre-A3) mapped
    # work -> work-backup and reported its folder_count; the canonical resolver leaves it unmapped.
    db, _root, ocfg, acfg = _env(tmp_path, file_key="work", structure_key="work-backup")
    h = source_index_health(SourceIndexRepository(db), ocfg, app_config=acfg)
    r = next(x for x in h["roots"] if x["root_key"] == "work")
    assert r["folder_count"] == 0
    assert r.get("structure_mapping_reason") == "unmapped"


def test_health_explicit_map_resolves_syn_prefixed_root(tmp_path):
    db, _root, ocfg, acfg = _env(tmp_path, file_key="syn-work", structure_key="work")
    acfg.source_structure.structure_root_map = {"syn-work": "work"}
    h = source_index_health(SourceIndexRepository(db), ocfg, app_config=acfg)
    r = next(x for x in h["roots"] if x["root_key"] == "syn-work")
    assert r["folder_count"] == 5
    assert r.get("structure_mapping_reason") == "explicit_map"


def test_health_and_watcher_readiness_agree_on_mapping(tmp_path):
    db, _root, ocfg, acfg = _env(tmp_path, file_key="work", structure_key="work-backup")
    # health resolves the structure mapping as unmapped; watcher readiness must agree (not ready).
    h = source_index_health(SourceIndexRepository(db), ocfg, app_config=acfg)
    r = next(x for x in h["roots"] if x["root_key"] == "work")
    run_state = sb.resolve_run_state(
        "work", db_path=db, obsidian_config=ocfg, app_config=acfg, backend_available=True
    )
    assert r["bootstrap"]["watcher_ready"] is False
    assert run_state == sb.RUN_STATE_NOT_BOOTSTRAPPED


def test_ephemeral_cli_override_cannot_certify_durable_readiness(tmp_path):
    # A CLI override that diverges from canonical config must fail closed for durable watcher readiness.
    db, _root, ocfg, acfg = _env(tmp_path, file_key="work", structure_key="work")
    diverging = {"work": "work-backup"}  # points somewhere other than the canonical exact match
    state = sb.resolve_run_state(
        "work",
        db_path=db,
        obsidian_config=ocfg,
        app_config=acfg,
        backend_available=True,
        explicit_map=diverging,
    )
    assert state == sb.RUN_STATE_MAPPING_OVERRIDE_NOT_PERSISTED


def test_no_absolute_paths_in_serialized_health(tmp_path):
    import json

    db, root, ocfg, acfg = _env(tmp_path, file_key="work", structure_key="work")
    h = source_index_health(SourceIndexRepository(db), ocfg, app_config=acfg)
    blob = json.dumps(h)
    assert str(root) not in blob
    assert str(tmp_path) not in blob


# ==================================================================================================
# fail-closed mapping-configuration loading: a failed/invalid load is NOT an empty valid config
# ==================================================================================================
def test_health_config_load_failure_fails_closed(tmp_path, monkeypatch):
    # app_config is NOT injected → health loads it internally. If the load RAISES, health must fail closed:
    # every root's mapping is `mapping_configuration_unavailable`, structure_ready False, and the top-level
    # availability flag is False. No identity fallback.
    db, _root, ocfg, _acfg = _env(tmp_path, file_key="work", structure_key="work")

    def _boom(*a, **k):
        raise OSError("config file unreadable")

    monkeypatch.setattr("hb_assistant.config.loader.load_config", _boom)
    h = source_index_health(SourceIndexRepository(db), ocfg)  # no app_config injected
    assert h["structure_mapping_config_available"] is False
    r = next(x for x in h["roots"] if x["root_key"] == "work")
    assert r["structure_mapping_reason"] == "mapping_configuration_unavailable"
    assert r["structure_key"] is None
    assert r["structure_ready"] is False
    assert r["folder_count"] == 0  # no identity fallback despite an ingested "work" structure root


def test_health_invalid_mapping_config_fails_closed(tmp_path, monkeypatch):
    # A config that fails validation (a genuinely invalid structure_root_map) is indistinguishable from
    # unavailable for trust purposes → fail closed, never structure-ready.
    db, _root, ocfg, _acfg = _env(tmp_path, file_key="work", structure_key="work")

    def _raise_validation(*a, **k):
        from hb_assistant.config.models import SourceStructureConfig

        # normalized-key collision with conflicting targets → pydantic ValidationError
        SourceStructureConfig(structure_root_map={"work": "a", "work ": "b"})

    monkeypatch.setattr("hb_assistant.config.loader.load_config", _raise_validation)
    h = source_index_health(SourceIndexRepository(db), ocfg)
    assert h["structure_mapping_config_available"] is False
    r = next(x for x in h["roots"] if x["root_key"] == "work")
    assert r["structure_mapping_reason"] == "mapping_configuration_unavailable"
    assert r["structure_ready"] is False


def test_valid_empty_config_still_allows_exact_identity_match(tmp_path):
    # An explicitly injected VALID config whose scan_roots is empty is trusted (distinct from a failed
    # load): exact identity matching against ingested structure roots still resolves.
    db, _root, ocfg, acfg = _env(tmp_path, file_key="work", structure_key="work")
    acfg.source_structure.scan_roots = {}  # valid, but declares no scan roots
    acfg.source_structure.structure_root_map = {}
    h = source_index_health(SourceIndexRepository(db), ocfg, app_config=acfg)
    assert h["structure_mapping_config_available"] is True
    r = next(x for x in h["roots"] if x["root_key"] == "work")
    assert r["structure_mapping_reason"] == "exact_match"
    assert r["structure_key"] == "work"
    assert r["structure_ready"] is True


def test_config_failure_cannot_report_structure_ready(tmp_path, monkeypatch):
    # Blanket guarantee: under a config-load failure NO root may be reported structure_ready.
    db, _root, ocfg, _acfg = _env(tmp_path, file_key="work", structure_key="work")

    monkeypatch.setattr(
        "hb_assistant.config.loader.load_config",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("load failed")),
    )
    h = source_index_health(SourceIndexRepository(db), ocfg)
    assert h["structure_mapping_config_available"] is False
    assert all(r["structure_ready"] is False for r in h["roots"])


# ==================================================================================================
# canonical config authority: validation rules + backward compatibility
# ==================================================================================================
def test_config_structure_root_map_defaults_empty_backward_compatible():
    from hb_assistant.config.models import SourceStructureConfig

    # An existing config with no structure_root_map still validates; the field defaults to {}.
    cfg = SourceStructureConfig(scan_roots={"work": "/x"})
    assert cfg.structure_root_map == {}
    # many-to-one is accepted
    cfg2 = SourceStructureConfig(structure_root_map={"syn-work": "work", "work-backup": "work"})
    assert cfg2.structure_root_map["work-backup"] == "work"


def test_config_structure_root_map_rejects_normalized_collision():
    import pytest
    from pydantic import ValidationError

    from hb_assistant.config.models import SourceStructureConfig

    with pytest.raises(ValidationError):
        SourceStructureConfig(structure_root_map={"work": "a", "work ": "b"})


def test_validate_structure_root_map_surfaces_config_errors():
    from hb_assistant.obsidian_mcp import source_root_mapping as srm

    errs = srm.validate_structure_root_map({"work": "missing"}, ["real"])
    assert any(e["reason"] == "invalid_explicit_map" for e in errs)
    # a valid many-to-one map produces no errors
    assert srm.validate_structure_root_map({"a": "s", "b": "s"}, ["s"]) == []
