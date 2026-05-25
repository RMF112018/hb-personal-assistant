"""ContentHasher: sha256 for downloaded files (and comparison with e_tag/c_tag)."""

from __future__ import annotations

import hashlib
from pathlib import Path

class ContentHasher:
    def hash_file(self, path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def matches(self, path: Path, expected_sha256: Optional[str]) -> bool:
        if not expected_sha256:
            return True
        return self.hash_file(path) == expected_sha256
