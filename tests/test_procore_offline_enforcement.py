"""AST-level guarantee that Procore unit tests never import a real HTTP client.

Phase 03 Prompt 12 codifies the existing convention: every Procore test must
use the injectable transport pattern from ``tests/test_procore_http_client.py``
(``FakeResponse`` + ``make_recording_transport``). A direct import of
``requests``, ``httpx``, ``urllib.request``, or ``urllib3`` in any
``tests/test_procore_*.py`` file silently re-introduces real-network risk.
"""

from __future__ import annotations

import ast
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent

FORBIDDEN_MODULES = {"requests", "httpx", "urllib.request", "urllib3"}


def _module_is_forbidden(name: str) -> bool:
    if name in FORBIDDEN_MODULES:
        return True
    return any(name.startswith(f"{m}.") for m in FORBIDDEN_MODULES)


def _scan_imports(path: Path) -> list[str]:
    violations: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _module_is_forbidden(alias.name):
                    violations.append(f"{path.name}:{node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if _module_is_forbidden(module):
                violations.append(f"{path.name}:{node.lineno}: from {module} import ...")
    return violations


def _procore_test_files() -> list[Path]:
    return sorted(TESTS_DIR.glob("test_procore_*.py"))


def test_procore_test_modules_use_injected_transport_only() -> None:
    files = _procore_test_files()
    assert files, "no tests/test_procore_*.py files discovered"

    violations: list[str] = []
    for path in files:
        violations.extend(_scan_imports(path))

    if violations:
        rendered = "\n".join(f"  - {v}" for v in violations)
        raise AssertionError(
            "Procore test files must not import real HTTP clients:\n"
            f"{rendered}\n"
            "Use the injectable transport pattern in tests/test_procore_http_client.py "
            "(FakeResponse + make_recording_transport) instead."
        )


def test_offline_enforcement_covers_more_than_one_file() -> None:
    files = _procore_test_files()
    assert len(files) >= 3, f"expected at least 3 procore test modules; found {len(files)}"
