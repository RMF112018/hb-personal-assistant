"""Phase 04 Prompt 02 — boundary proof that the client secret is not reachable
from the bearer-token path.

The OAuth client secret in ``hb_assistant.procore.config.get_procore_client_secret``
is reserved for the (future) OAuth exchange / refresh path. Any other Procore
source module importing or calling that symbol would silently re-introduce the
Phase 04 Prompt 01 hazard (the client secret being used as a bearer).

These tests scan ``src/hb_assistant/procore/`` and fail with a precise location
if any file outside the allowlist references the symbol.
"""

from __future__ import annotations

import ast
from pathlib import Path

PROCORE_SRC = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "hb_assistant"
    / "procore"
)

# Files that may legitimately mention the symbol:
# - config.py: the canonical implementation site.
# - errors.py: docstring for ProcoreAuthRequired explains the hazard it guards against.
# - redaction.py: module docstring enumerates client_secret as a redaction scope.
ALLOWLIST_FILES = {"config.py", "errors.py", "redaction.py"}


def _procore_source_files() -> list[Path]:
    files: list[Path] = []
    for path in PROCORE_SRC.rglob("*.py"):
        if any(part in {"__pycache__", "tests"} for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def test_client_secret_symbol_not_imported_outside_allowlist() -> None:
    violations: list[str] = []
    for path in _procore_source_files():
        if path.name in ALLOWLIST_FILES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if any(alias.name == "get_procore_client_secret" for alias in node.names):
                    violations.append(f"{path.relative_to(PROCORE_SRC.parents[3])}:{node.lineno}: from-import")
            elif isinstance(node, ast.Import):
                # `import hb_assistant.procore.config` is benign — only flag direct symbol import.
                pass
            elif isinstance(node, ast.Attribute):
                if node.attr == "get_procore_client_secret":
                    violations.append(
                        f"{path.relative_to(PROCORE_SRC.parents[3])}:{node.lineno}: attribute access"
                    )
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "get_procore_client_secret":
                    violations.append(
                        f"{path.relative_to(PROCORE_SRC.parents[3])}:{node.lineno}: direct call"
                    )

    if violations:
        rendered = "\n".join(f"  - {v}" for v in violations)
        raise AssertionError(
            "Procore source modules outside the allowlist must not import or "
            "call get_procore_client_secret (Phase 04 Prompt 01 hazard):\n"
            f"{rendered}"
        )


def test_bearer_authorization_header_only_built_from_token_provider() -> None:
    """``_build_headers`` in ``http_client.py`` sources the bearer string from
    ``self._access_token_provider.get_access_token()`` and the module performs
    no import / attribute access / call of ``get_procore_client_secret``.
    The first test already enforces the boundary at AST level for every file
    in ``procore/`` outside the allowlist; this test is the focused
    http_client-specific witness.
    """
    http_client_path = PROCORE_SRC / "http_client.py"
    src = http_client_path.read_text(encoding="utf-8")
    assert "self._access_token_provider.get_access_token()" in src

    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and any(
            alias.name == "get_procore_client_secret" for alias in node.names
        ):
            raise AssertionError(
                f"http_client.py:{node.lineno} imports get_procore_client_secret "
                "(Phase 04 Prompt 01 hazard)"
            )
        if isinstance(node, ast.Attribute) and node.attr == "get_procore_client_secret":
            raise AssertionError(
                f"http_client.py:{node.lineno} references get_procore_client_secret "
                "(Phase 04 Prompt 01 hazard)"
            )
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "get_procore_client_secret"
        ):
            raise AssertionError(
                f"http_client.py:{node.lineno} calls get_procore_client_secret "
                "(Phase 04 Prompt 01 hazard)"
            )
