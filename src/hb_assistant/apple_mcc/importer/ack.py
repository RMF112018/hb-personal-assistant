"""Importer acknowledgements for spool checkpoint gate."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ImportAck:
    batch_id: str
    status: str  # accepted | rejected
    item_count: int
    detail: str = ""

    def write(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "batch_id": self.batch_id,
                    "status": self.status,
                    "item_count": self.item_count,
                    "detail": self.detail,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
