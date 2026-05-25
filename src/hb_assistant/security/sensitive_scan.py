"""Bounded content sensitive scanner.

Scans configured paths safely and reports only category/path/line/severity metadata.
Never emits matched secret values.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy


@dataclass
class ScanConfig:
    max_file_size_bytes: int = 512_000
    max_lines_per_file: int = 2000
    max_files: int = 5000
    high_risk_extensions: tuple[str, ...] = (".env", ".pem", ".key", ".pfx", ".json")


@dataclass
class Finding:
    category: str
    path: str
    line: int
    severity: str
    rule_id: str
    hint: str | None = None


_RULES: list[tuple[str, str, str, str, re.Pattern[str], str | None]] = [
    ("pem_private_key", "critical", "SEC-PEM-001", "pem_private_key", re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"), "Private key header detected"),
    ("pem_block", "high", "SEC-PEM-002", "pem_block", re.compile(r"-----BEGIN [A-Z0-9 ]+-----"), "PEM-like block header detected"),
    ("jwt_like", "high", "SEC-TOK-001", "jwt_like", re.compile(r"\beyJ[a-zA-Z0-9_-]{8,}\.[a-zA-Z0-9_-]{8,}\.[a-zA-Z0-9_-]{8,}\b"), "JWT-like token structure"),
    ("oauth_access_token_field", "high", "SEC-TOK-002", "oauth_access_token_field", re.compile(r"\b(access_token|refresh_token|id_token)\b\s*[:=]", re.IGNORECASE), "OAuth token field assignment"),
    ("client_secret_assignment", "critical", "SEC-TOK-003", "client_secret_assignment", re.compile(r"\bclient[_-]?secret\b\s*[:=]", re.IGNORECASE), "Client secret assignment"),
    ("bearer_token", "high", "SEC-TOK-004", "bearer_token", re.compile(r"\bBearer\s+[A-Za-z0-9._\-+/=]{16,}"), "Bearer token pattern"),
    ("env_secret_assignment", "high", "SEC-ENV-001", "env_secret_assignment", re.compile(r"^\s*([A-Z0-9_]*(SECRET|TOKEN|PASSWORD|API_KEY|CLIENT_SECRET)[A-Z0-9_]*)\s*=\s*.+$", re.IGNORECASE), ".env-style secret assignment"),
    ("msal_cache_content", "medium", "SEC-MSAL-001", "msal_cache_content", re.compile(r"\b(msal|token_cache|refresh_token|access_token)\b", re.IGNORECASE), "MSAL/token cache indicator"),
]


class SensitiveScanner:
    def __init__(self, config: ScanConfig | None = None) -> None:
        self.config = config or ScanConfig()

    def _display_path(self, p: Path, repo_root: Path) -> str:
        try:
            return str(p.relative_to(repo_root))
        except Exception:
            return str(p).replace(str(Path.home()), "~")

    def _is_binary(self, path: Path) -> bool:
        try:
            with path.open("rb") as f:
                chunk = f.read(2048)
            if b"\x00" in chunk:
                return True
            chunk.decode("utf-8")
            return False
        except Exception:
            return True

    def _should_exclude(self, path: Path) -> bool:
        text = str(path)
        exclusions = ["/.git/", "/.venv/", "/__pycache__/", "/.mypy_cache/", "/.pytest_cache/", "/node_modules/"]
        return any(e in text for e in exclusions)

    def _scan_file(self, path: Path, repo_root: Path) -> tuple[list[Finding], dict[str, int]]:
        stats = {"scanned": 0, "binary_skipped": 0, "oversize_skipped": 0, "read_errors": 0}
        findings: list[Finding] = []

        ext = path.suffix.lower()
        try:
            size = path.stat().st_size
        except Exception:
            stats["read_errors"] += 1
            return findings, stats

        high_risk = ext in self.config.high_risk_extensions or path.name.lower().startswith(".env")
        if size > self.config.max_file_size_bytes and not high_risk:
            stats["oversize_skipped"] += 1
            return findings, stats

        if self._is_binary(path):
            stats["binary_skipped"] += 1
            return findings, stats

        try:
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                for lineno, line in enumerate(f, start=1):
                    if lineno > self.config.max_lines_per_file:
                        break
                    for category, severity, rule_id, _key, pattern, hint in _RULES:
                        if pattern.search(line):
                            findings.append(
                                Finding(
                                    category=category,
                                    path=self._display_path(path, repo_root),
                                    line=lineno,
                                    severity=severity,
                                    rule_id=rule_id,
                                    hint=hint,
                                )
                            )
            stats["scanned"] += 1
        except Exception:
            stats["read_errors"] += 1
        return findings, stats

    def scan(self, repo: str = ".") -> dict[str, Any]:
        pp = PathPolicy()
        repo_root = Path(repo).resolve()

        targets = [repo_root]
        try:
            app_support = pp.get_app_support()
            targets.append(app_support)
            targets.append(app_support / "evidence")
        except Exception:
            pass

        total_stats = {
            "files_considered": 0,
            "files_scanned": 0,
            "files_binary_skipped": 0,
            "files_oversize_skipped": 0,
            "files_read_errors": 0,
            "files_excluded": 0,
        }
        findings: list[Finding] = []

        for base in targets:
            if not base.exists():
                continue
            try:
                iterator = base.rglob("*")
            except Exception:
                continue
            for p in iterator:
                if len(findings) >= self.config.max_files:
                    break
                if not p.is_file():
                    continue
                total_stats["files_considered"] += 1
                if self._should_exclude(p):
                    total_stats["files_excluded"] += 1
                    continue
                fnd, st = self._scan_file(p, repo_root)
                findings.extend(fnd)
                total_stats["files_scanned"] += st["scanned"]
                total_stats["files_binary_skipped"] += st["binary_skipped"]
                total_stats["files_oversize_skipped"] += st["oversize_skipped"]
                total_stats["files_read_errors"] += st["read_errors"]

        findings_by_category: dict[str, list[str]] = {}
        for f in findings:
            findings_by_category.setdefault(f.category, [])
            if f.path not in findings_by_category[f.category]:
                findings_by_category[f.category].append(f.path)

        return {
            "implemented": True,
            "phase": 12,
            "repo": repo,
            "scanned_paths": [str(t).replace(str(Path.home()), "~") for t in targets],
            "findings": [asdict(f) for f in findings],
            "findings_by_category": findings_by_category,
            "stats": total_stats,
            "note": "Bounded content scan with redacted output fields only; no matched secret values emitted.",
        }
