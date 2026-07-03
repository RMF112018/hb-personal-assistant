"""Static safety tests for the NAS runtime scaffold (Phase N1B).

These assert the scaffold's safety invariants without importing the app, touching any DB,
starting a server, or reaching the NAS. They are the executable form of docs/evidence
05-safety-invariants.md.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
NAS = REPO_ROOT / "deploy" / "nas"
COMPOSE = NAS / "compose.yaml"
DOCKERFILE = NAS / "Dockerfile"
NAS_CFG = NAS / "hb-pa-config.nas.example.yml"
SMOKE_CFG = NAS / "hb-pa-config.smoke.example.yml"
DOCKERIGNORE = REPO_ROOT / ".dockerignore"


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _strip_comments(text: str) -> str:
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def active(p: Path) -> str:
    """File content with # comments removed — so forbidden strings in explanatory comments
    do not trip absence assertions."""
    return _strip_comments(read(p))


def test_scaffold_files_exist() -> None:
    for p in (COMPOSE, DOCKERFILE, NAS_CFG, SMOKE_CFG, DOCKERIGNORE):
        assert p.is_file(), f"missing scaffold file: {p.relative_to(REPO_ROOT)}"


def test_compose_publishes_port_8000() -> None:
    assert ":8000:8000" in read(COMPOSE)


def test_compose_disables_background_workers() -> None:
    assert 'HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS: "1"' in read(COMPOSE)


def test_compose_sets_hb_pa_config() -> None:
    assert "HB_PA_CONFIG: /config/hb-pa-config.yml" in read(COMPOSE)


def test_compose_publish_defaults_to_loopback_not_wildcard() -> None:
    text = read(COMPOSE)
    assert "${HB_PUBLISH_ADDR:-127.0.0.1}" in text
    assert "0.0.0.0:8000" not in text


def test_compose_has_no_volumes_smb_path() -> None:
    assert "/Volumes" not in active(COMPOSE)


def test_compose_does_not_mount_mac_app_support() -> None:
    assert "Library/Application Support" not in active(COMPOSE)


def test_compose_does_not_mount_live_vault() -> None:
    assert "Documents/Obsidian Vault" not in active(COMPOSE)


def test_compose_restart_policy_is_not_always() -> None:
    text = read(COMPOSE)
    assert 'restart: "always"' not in text
    assert 'restart: "unless-stopped"' not in text


def test_compose_mounts_config_read_only() -> None:
    assert ":/config/hb-pa-config.yml:ro" in read(COMPOSE)


def test_compose_has_no_scheduler_or_watcher_service() -> None:
    # No service/key whose name implies a scheduler or source watcher.
    assert not re.search(r"^\s+(scheduler|source-?watcher|watcher)[a-z-]*:", read(COMPOSE), re.I | re.M)


def test_dockerfile_uses_factory_and_wildcard_bind_internally() -> None:
    text = read(DOCKERFILE)
    assert "analytics.api:create_app" in text
    assert '"--factory"' in text
    assert '"0.0.0.0"' in text  # container-internal bind; host exposure controlled by compose


def test_dockerfile_installs_analytics_ui_extra() -> None:
    assert ".[analytics-ui]" in read(DOCKERFILE)


def test_dockerfile_python_312_or_newer_and_nonroot() -> None:
    text = read(DOCKERFILE)
    assert re.search(r"^FROM python:3\.(1[2-9]|[2-9]\d)", text, re.M), "base image must be python >=3.12"
    assert "USER hbsvc" in text


def test_nas_config_uses_nas_local_app_support() -> None:
    text = active(NAS_CFG)
    assert "application_support_root: /volume1/personal-assistant/app-support" in text
    assert "/Volumes" not in text
    assert "Library/Application Support" not in text


def test_smoke_config_uses_separate_scratch_root() -> None:
    text = active(SMOKE_CFG)
    assert "app-support-smoke" in text
    # must NOT point at the live app-support root
    assert not re.search(
        r"application_support_root:\s*/volume1/personal-assistant/app-support\s*$", text, re.M
    )


def test_dockerignore_excludes_config_db_and_secrets() -> None:
    text = read(DOCKERIGNORE)
    # Config, DB, env, and secret FILES must be excluded from the build context.
    for needed in (
        "config/config.yml",
        "**/.env",
        "**/*.sqlite",
        "**/*.db",
        "**/*.key",
        "**/*.pem",
        "**/msal-token-cache*.bin",
        "**/text-vault.key",
    ):
        assert needed in text, f".dockerignore missing safety exclusion: {needed}"


def test_dockerignore_does_not_exclude_source_packages() -> None:
    # N1C fix: `.dockerignore` must exclude secret FILES, never directories named
    # auth/ or security/ — those are real source packages (src/hb_assistant/{auth,security}/)
    # and excluding them stripped the packages from the image (ModuleNotFoundError at boot).
    # Compare on comment-stripped content so the explanatory NOTE naming these dirs is ignored.
    active_text = active(DOCKERIGNORE)
    for bad in ("**/auth/", "**/security/", "src/hb_assistant/auth", "src/hb_assistant/security"):
        assert bad not in active_text, (
            f".dockerignore must not exclude source packages via '{bad}' "
            "(src/hb_assistant/{auth,security}/ are real packages — see the N1C fix)"
        )


def test_no_secret_values_in_scaffold_files() -> None:
    # Scope to config-bearing files (not scripts, which legitimately contain detection keywords),
    # and ignore comments.
    secret_re = re.compile(
        r"-----BEGIN|(client_secret|password|access_token|refresh_token|api_key|fernet)\s*[:=]\s*[\"']?[A-Za-z0-9/_+.-]{12,}",
        re.I,
    )
    targets = [COMPOSE, DOCKERFILE, NAS_CFG, SMOKE_CFG, NAS / ".env.example"]
    offenders = [
        str(p.relative_to(REPO_ROOT))
        for p in targets
        if p.is_file() and secret_re.search(_strip_comments(read(p)))
    ]
    assert not offenders, f"possible secret material in: {offenders}"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
